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
import shutil
import platform
import traceback
import sys
import time
import datetime
import serial
import select
import struct

import serial.tools.list_ports
from dataclasses import dataclass
from asyncio.subprocess import PIPE,STDOUT
from enum import IntEnum
from typing import NamedTuple
import logging

from device_comms_base import DeviceCommsBase, StartupStatus

# Create a logging object with a null handler. if the caller of this class
# does not configure a logger context then no messages will be printed.
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

@dataclass
class SerialCommsDeviceConfig:
    serial_device_path: str # device path or com port to serial device
    baud_rate: str = None # optionally set the baudrate

class SerialCommsDevice(DeviceCommsBase):

    def __init__(self, config_object):

        super().__init__()

        assert isinstance(config_object, SerialCommsDeviceConfig), "config must be of type SerialCommsDeviceConfig"

        self.config = config_object

    def __device_connected(self, device: str) -> bool:
        """Check if the given device is connected by comparing it against
        the list of available serial ports on the system."""

        ports = [p.device for p in serial.tools.list_ports.comports()]
        return device in ports

    def __get_device_path(self) -> str:
        """
        Returns the proper device path.
        On Linux, expand user and get absolute path.
        On Windows, use the provided path directly.
        """

        if platform.system() == "Linux":
            return os.path.abspath(os.path.expanduser(self.config.serial_device_path))
        else:
            return self.config.serial_device_path

    def __logging_service_thread(self, startup_complete_event_listener: threading.Event):
        """Internal thread method for capturing incoming serial data."""

        logger.debug("Starting logging service thread... [" + str(self.config.serial_device_path) + "]")

        device = self.__get_device_path()
        #if not self.__device_connected(device):
        #    logger.debug("Failed to open: device " + device + " is not connected")
        #    print("Failed to open: device " + device + " is not connected")
        #    with self.thread_mgmt_lock:
        #        self.startup_status = StartupStatus.ERROR
        #    startup_complete_event_listener.set()  # In case of error, unblock startup
        #    return

        try:

            with serial.Serial(self.config.serial_device_path, self.config.baud_rate) as ser:

                if ser is None:
                    raise Exception("Could not begin uart logging")

                print("event listener set...")

                with self.thread_mgmt_lock:
                    self.startup_status = StartupStatus.SUCCESS

                # Signal to the caller that the hardware is in a good state.
                startup_complete_event_listener.set()

                while not self.stop_requested.isSet():

                    data_read = False
                    data_written = False

                    if ser.in_waiting:
                        data_read = True
                        # Read and decode the trace
                        #trace = ser.readline().decode("utf-8").strip()
                        trace = ser.readline().decode("latin-1").strip()

                        if len(trace) == 0:
                            continue

                        #logger.log(logging.DEBUG, trace)
                        print(f"<-- {trace}")

                        # Put the trace into the read_queue
                        if self.read_queue is not None:
                            self.read_queue.put(trace)
                        else:
                            raise Exception("No logging queue available")

                    if not self.write_queue.empty():
                        data_written = True

                        cmd = self.write_queue.get_nowait()

                        if cmd is not None:
                            logger.debug(f"--> {cmd}")
                            ser.write( (cmd + "\n").encode("latin-1") )

                    # if we're not doing anything give time back to the CPU
                    if not data_read and not data_written:
                        time.sleep(0.005)

        except Exception as e:
            logger.error("Logging service encountered an error: " + str(e))
            traceback.print_exc()

            with self.thread_mgmt_lock:
                self.startup_status = StartupStatus.ERROR

            startup_complete_event_listener.set()  # In case of error, unblock startup

    def is_capturing_traces(self) -> bool:
        """Return True if the logging (read) thread is actively capturing traces."""

        return hasattr(self, 'logging_thread') and self.logging_thread.is_alive()

    def _start_capturing_traces(self, startup_complete_event):
        """Start capturing the logs of a given device.
           Return only once we have feedback that the hardware is in a good state.
        """

        self.acquire_hardware_mutex()

        # Start the logging thread
        self.logging_thread = threading.Thread(
            target=self.__logging_service_thread,
            args=(startup_complete_event,),
            daemon=True
        )

        print("starting serial thread ...")
        self.logging_thread.start()

        self.release_hardware_mutex()

        # Wait until the logging thread signals that hardware is ready.
        logger.debug("Started capturing traces.")

    def _stop_capturing_traces(self):
        """Stop capturing logs. This will stop all services running on your machine
           that interact with the end device.
        """

        self.stop_requested.set()

        if hasattr(self, 'logging_thread') and self.logging_thread.is_alive():
            self.logging_thread.join()

        logger.debug("Stopped capturing traces.")

