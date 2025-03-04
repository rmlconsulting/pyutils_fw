################################################################################
#
# BSD 2-Clause License
#
# Copyright (c) 2025, RML Consulting, LLC
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
################################################################################

import queue
import threading
import subprocess
import re
import os
import sys
import time
import select
from asyncio.subprocess import PIPE,STDOUT
from enum import IntEnum
import logging
from dataclasses import dataclass
from device_comms_base import DeviceCommsBase, StartupStatus

# Create a logging object with a null handler. if the caller of this class
# does not configure a logger context then no messages will be printed.
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

class JLinkTransportInterface(IntEnum):
    SWD = 1
    #SWO = 2 #untested
    #JTAG = 3 #untested

@dataclass
class JLinkTransportConfig:
    target_device: str # something like NRF52832_XXAA or STM32G491VE
    debugger_sn: str = None # when running more than 1 debugger
    interface: JLinkTransportInterface = JLinkTransportInterface.SWD
    speed: int = 64000
    hardware_recovery_time_sec: int = 0

class JLinkComms(DeviceCommsBase):

    last_telnet_port_used = 30000

    # Class-level lock for modifying class vars
    lock = threading.Lock()

    def __init__(self, config_object):

        assert isinstance(config_object, JLinkTransportConfig), \
                "JlinkTransport config param must be an instance of JlinkTransportConfig"

        super().__init__( hardware_recovery_time_sec = config_object.hardware_recovery_time_sec)

        self.__config = config_object
        self.__telnet_port = None
        self.__jlink_process = None
        self.__logging_process = None

    def __str__(self):
        return f"JLinkDevice(server port:{self.__telnet_port}. isLogging:{self._is_logging.isSet()}. stop:{self._stop_requested.isSet()}"

    def send_cmd_to_link_management(self, cmd):
        """
        send a command to the jlink server. See reference at:
        https://kb.segger.com/J-Link_Commander
        """
        if self.__jlink_process:
            logger.debug(f"sending cmd to jlink: {cmd}")
            self.__jlink_process.stdin.write(cmd)
            self.__jlink_process.stdin.flush()
            return True
        else:
            logger.debug("Not connected to jlink")
            return False

    def __start_jlink_server(self, telnet_port, shutdown_request):
        """
         start the jlink server in its own thread. i.e. JLinkExe
         caller should hold the debugger mutex
        """

        jlink_process_cmd = 'JLinkExe ' + \
                               f" -device {self.__config.target_device} " + \
                               f" -speed {self.__config.speed} " + \
                               " -if SWD " + \
                               " -autoconnect 1 " + \
                               f" -RTTTelnetport {self.__telnet_port}"

        if self.__config.debugger_sn:
            jlink_process_cmd += f" -SelectEmuBySn {self.__config.debugger_sn}"

        logger.debug(f"Starting jlink with comd: {jlink_process_cmd}")

        self.__jlink_process = subprocess.Popen(
                                   ['/bin/sh', '-c', jlink_process_cmd],
                                   encoding="ISO-8859-1",
                                   stdout=subprocess.PIPE,
                                   stdin=subprocess.PIPE,
                                   stderr=subprocess.PIPE)

        now = lambda: int(round(time.time()) * 1000)
        start_ms = now()
        timeout_ms = 5000

        #default to error condition
        success = False

        jlink_output = ""

        while(now() - start_ms < timeout_ms):

            if shutdown_request.isSet():
                logger.info("SHUTDOWN REQUESTED....")
                break

            line = ""

            #line = await asyncio.wait_for(self.__logging_process.stdout.readline(), 1)
            #TODO: this wont work on windows, ... how should we do
            # non blocking reads? the process above works except theres
            # no way to kill the process when no logs are being
            # generated
            # other approaches: asyncio
            pending_read_fds = select.select([self.__jlink_process.stdout],
                                        [],
                                        [],
                                        0.25)[0]

            if (len(pending_read_fds) > 0):

                line = self.__jlink_process.stdout.readline().strip()
                print(line)

                jlink_output += line + "\r\n"

                # check for ERRORs
                if ("Cannot connect to target" in line or
                    "JLinkARM DLL reported an error" in line or
                    "Connecting to J-Link via USB...FAILED" in line):

                    # only logger.debug out the logs for a failure case
                    logger.debug(jlink_process_cmd)
                    logger.debug(jlink_output)
                    logger.error(f"Detected error on jlink server setup:{line}")
                    return False

                # TODO: make this generic
                elif "Cortex-M4 identified" in line:
                    return True

            else:
                # sometimes the end of the bootup process seems to hang,
                # by experimentation, it looks like any command sent will
                # flush out the rest of the stdout from the jlink

                #self.__jlink_process.stdin.write("ShowEmuList\r\n")
                #self.__jlink_process.stdin.write("reset\r\n")

                # send the command that un-halts devices
                self.__jlink_process.stdin.write("go\r\n")
                self.__jlink_process.stdin.flush()

        return success

    # start the logging process thread. (e.g. JLinkRTTClient or JLinkSWOViewer)
    # caller should hold the debugger mutex
    def __start_logging_process(self, telnet_port, stop_requested):

        logging_process_cmd = 'JLinkRTTClient -RTTTelnetPort ' + str(telnet_port)

        #logger.debug("starting rtt [" + jlink_process_cmd + "]")
        self.__logging_process = subprocess.Popen(
                                          ['/bin/sh', '-c',
                                          logging_process_cmd],
                                          stdout=subprocess.PIPE,
                                          bufsize=1,
                                          universal_newlines=True,
                                          encoding="ISO-8859-1")

        #TODO: add a timeout for this step as in other log processing requests
        #      and detect errors, if any are logger.debuged here
        # get rid of the segger jlink header garbage
        for line in self.__logging_process.stdout:

            if stop_requested.isSet():
                return false

            if re.search("Process: JLinkExe", line):
                break

        return True

    def __logging_service_thread(self, startup_complete_event_listener, shutdown_request):

        # increment the telnet port... reserving the last number for our use
        with JLinkComms.lock:
            JLinkComms.last_telnet_port_used += 1
            self.__telnet_port = JLinkComms.last_telnet_port_used - 1

        print(f"start jlink server on port {self.__telnet_port}")
        # startup jlinkexe
        success = self.__start_jlink_server(self.__telnet_port, shutdown_request)

        if not success:
            logger.debug("ERROR: Aborting test. Failed to bringup JLink Server")

            with JLinkDevice.thread_mgmt_lock:
                self._startup_status = StartupStatus.ERROR

            startup_complete_event_listener.set()

            # otherwise just raise and exception
            raise Exception('Failed to init JLinkServer')

        # give a moment to stabalize. unpredictable things tend to happen if
        # you hit jlink's driver too hard
        time.sleep(0.5)

        logger.debug("staring logging process on port [" + str(self.__telnet_port) + "...")
        self.__start_logging_process(self.__telnet_port, self._stop_requested)

        time.sleep(0.25)

        with self._thread_mgmt_lock:
            self._startup_status = StartupStatus.SUCCESS

        # signal to the caller that we're done with the startup process.
        startup_complete_event_listener.set()

        # capture data from the device and stick it in our queue
        while( True ):
            line = None

            #TODO: this wont work on windows, ... how should we do
            # non blocking reads? the process above works except theres
            # no way to kill the process when no logs are being
            # generated
            # other approaches: asyncio -> doesn't support timeouts
            poll_result = select.select([self.__logging_process.stdout], [],[], 0.25)[0]

            # poll will return the fds that are ready. array entry 0 is the
            # fd ready for reading. we only were looking for read on stdout
            # so if we have something stdout will not block
            if (len(poll_result) > 0):
                with self._hardware_mutex:
                    line = self.__logging_process.stdout.readline().strip()

                if (len(line) == 0):
                    continue

                logger.debug(line)

                self.read_queue.put(line)

            if (self._stop_requested.isSet()):

                logger.debug("process logging stop request")

                if (self.__logging_process is not None):
                    self.__logging_process.kill()

                self.__logging_process = None

                if (self.__jlink_process is not None):
                    self.__jlink_process.kill()

                self.__jlink_process = None

                break

    ###########################################################################
    # public  functions
    ###########################################################################

    # start capturing the logs of a given device.
    def _start_capturing_traces(self, startup_complete_event):

        self.acquire_hardware_mutex()

        self.__log_thread = threading.Thread(target = self.__logging_service_thread,
                                           args = [startup_complete_event, self._stop_requested],
                                           daemon=True)
        self.__log_thread.start()

        logger.debug("logging thread running...")

        self.release_hardware_mutex()

    # stop capturing logs. this will stop all services running on your machine
    # that interact with the debugger
    # TODO: confirm if this allows accessories to go to sleep. it might require
    #       a reset after logging is started before normal operation is resumed
    def _stop_capturing_traces(self):

        # to kill jlink process when doing something else, like 'nrfjprog -r'
        # can cause the jlink driver to go crazy
        self.acquire_hardware_mutex()

        try:
            if (self.__logging_process and self.__logging_process.poll() is not None):
                self.__logging_process.communicate()
        except:
            logger.debug("logging process hung... cant stop it nicely. killing it")

        # if the process exists and is still running then we have to terminate
        # it from here
        if (self.__logging_process and self.__logging_process.poll() is not None):
            logger.debug("nuking logging process...")
            self.__logging_process.kill()
            self.__logging_process = None

        # if the process exists and is still running then we have to terminate
        # it from here
        if (self.__jlink_process and self.__jlink_process.poll() is not None):
            logger.debug("nuking jlink process")
            self.__jlink_process.kill()
            self.__jlink_process = None

        self.__log_thread.join()
        self.__log_thread = None

        self.release_hardware_mutex()

