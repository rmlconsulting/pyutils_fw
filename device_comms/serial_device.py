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

import threading
import os
import platform
import traceback
import time
import serial

import serial.tools.list_ports
from dataclasses import dataclass
import logging

from device_comms_base import DeviceCommsBase, StartupStatus

# Create a logging object with a null handler. if the caller of this class
# does not configure a logger context then no messages will be printed.
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

@dataclass
class SerialCommsDeviceConfig:
    serial_device_path: str # device path or com port to serial device
    baud_rate: int # set the baudrate
    name: str = "SerialCommsDevice" # just for sensible logs
    device_recovery_time: int = 0 # amount of time needed before reconnecting
                                  # once disconnected

class SerialCommsDevice(DeviceCommsBase):

    def __init__(self, config_object):

        assert isinstance(config_object, SerialCommsDeviceConfig), \
                "config must be of type SerialCommsDeviceConfig"

        super().__init__(name = config_object.name,
                         hardware_recovery_time_sec = config_object.device_recovery_time)

        self.__config = config_object
        self.__shutdown_complete = threading.Event()
        self.__logging_thread = None

    def __str__(self):
        """ Stringify the SerialCommsDevice object """

        return f"SerialCommsDevice(path:{self.__config.serial_device_path}." + \
               f" baudrate:{self.__config.baud_rate}." + \
               f" isLogging:{self._is_logging.is_set()}." + \
               f" stop:{self._stop_requested.is_set()}" + \
               ")"

    def __logging_service_thread(self, startup_complete_event_listener: threading.Event):
        """ Internal thread method for capturing incoming serial data.
            This thread is responsible for taking data from the target device
            and placing it in the read_queue. also taking data from the
            write_queue and sending it out to the target device.
        """

        logger.debug(f"Starting logging service thread... [{self.__config.serial_device_path}]")

        device_path = self.does_device_exist( self.__config.serial_device_path )

        if not device_path:

            logger.error(f"Error: Failed to open: device {self.__config.serial_device_path} is not connected")
            with self._thread_mgmt_lock:
                self._startup_status = StartupStatus.ERROR
            startup_complete_event_listener.set()
            return

        try:

            with serial.Serial(device_path, self.__config.baud_rate, timeout=0.25) as ser:

                if ser is None:
                    raise Exception("Could not begin uart logging")

                with self._thread_mgmt_lock:
                    self._startup_status = StartupStatus.SUCCESS

                # Signal to the caller that the hardware is in a good state.
                startup_complete_event_listener.set()

                while not self._stop_requested.is_set():

                    acquired = self.acquire_hardware_mutex( timeout_ms = 100,
                                                            except_on_fail = False)

                    # this most commonly happens when the shutdown request is
                    # set at just the wrong time
                    if not acquired:
                        logger.debug("mutex not acquired. skipping")
                        continue

                    data_read = False
                    data_written = False

                    # pick up any data pending on the serial bus
                    if ser.in_waiting:
                        # Read and decode the trace
                        trace = ser.readline().decode("latin-1").strip()

                        if len(trace) > 0:
                            data_read = True

                            logger.info(f"<-- {trace}")

                            # Put the trace into the read_queue
                            if self.read_queue is not None:
                                self.read_queue.put_nowait(trace)
                            else:
                                raise Exception("No logging queue available")


                    # handle outgoing commands to send
                    if not self.write_queue.empty():

                        cmd = self.write_queue.get_nowait()

                        if cmd is not None:
                            data_written = True
                            logger.info(f"--> {cmd}")
                            ser.write( (f"{cmd}\n").encode("latin-1") )

                    self.release_hardware_mutex()

                    # if we're not doing anything give time back to the CPU
                    if not data_read and not data_written:
                        time.sleep(0.005)

        except Exception as e:
            self.release_hardware_mutex()
            logger.error("Logging service encountered an error: " + str(e))
            traceback.print_exc()

            with self._thread_mgmt_lock:
                self._startup_status = StartupStatus.ERROR

            startup_complete_event_listener.set()  # In case of error, unblock startup
            raise(e)

        logger.debug("logging thread shutdown")

        self.__shutdown_complete.set()

    def _start_capturing_traces(self, startup_complete_event):
        """Start capturing the logs of a given device.
           Return only once we have feedback that the hardware is in a good state.
        """

        # Start the logging thread
        self.__logging_thread = threading.Thread(
            target=self.__logging_service_thread,
            args=(startup_complete_event,),
            #daemon=True
        )

        self.__shutdown_complete.clear()
        self._stop_requested.clear()

        logger.info("starting serial thread ...")
        self.__logging_thread.start()

        # Wait until the logging thread signals that hardware is ready.
        logger.debug("Started capturing traces.")

    def _send_cmd_to_link_management(self, cmd) -> None:
        logger.debug("ignoring link management msg. not supported for serial comms")
        pass

    def _stop_capturing_traces(self):
        """Stop capturing logs. This will stop all services running on your machine
           that interact with the end device.
        """

        # wait for the serial thread to complete shutdown
        self.__shutdown_complete.wait()

        if self.__logging_thread is not None and self.__logging_thread.is_alive():
            logger.debug("joining logging thread")
            self.__logging_thread.join()

        logger.debug("Stopped capturing traces.")

