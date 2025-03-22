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
import re
import serial
import time
import logging
import struct
from dataclasses import dataclass

# Create a logging object with a null handler. if the caller of this class
# does not configure a logger context then no messages will be printed.
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

__now_ms = lambda: round(time.time() * 1000)

class LCUSRelayBoard():

    def __init__(self, path, num_relays):

        self.path = os.path.expanduser( os.path.abspath(path) )

        if not os.path.exists( self.path ):
            raise Exception("Could not open Relay path: " + str(path) )

        self.mutex      = threading.RLock()
        self.serial     = serial.Serial( self.path, \
                                         baudrate=9600, \
                                         bytesize=8, \
                                         parity='N', \
                                         stopbits=1, \
                                         timeout=1 )
        self.num_relays = num_relays

        self.relay_status = []
        logger.debug(f"initialized: {self}")

    def __str__(self):
        description = "LCUS Relay Board (" + str(self.num_relays) + " relays. path: " + str(self.path) + ")"

        return description

    def __execute_cmd(self, cmd):

        response = ''

        with self.mutex:
            logger.debug("sending: " + str(cmd))
            self.serial.write( cmd )

            if self.serial.in_waiting > 0:
                # if you have a relay board with 4 or more channels, you can
                # execute a status cmd
                response = self.serial.read( self.serial.in_waiting )

                logger.debug("response = [" + str(response) + "]")

        return response

    def __activate_relay(self, channel, is_active):
        # RELAY CMD FORMAT: <preamble> <channel> <is active 0/1> <cmd sum>

        CMD_PREAMBLE = 0xA0

        # boolean to int
        active_byte = int(is_active)

        # LC starts counting at 1. AS interfaces standardize on counting from 0 for
        # all relay modules so add 1 just before we send the command
        channel += 1

        cmd_sum = CMD_PREAMBLE + channel + active_byte

        cmd_bytes = struct.pack("<BBBB", CMD_PREAMBLE, channel, active_byte, cmd_sum)

        self.__execute_cmd(cmd_bytes)

    def status_inquiry(self):

        if (self.num_relays < 4):
            raise Exception("only LCUS relay boards with 4+ channels support the status inquiry")

        return self.__execute_cmd(0xFF)

    def relay_activate(self, relay_number):

        if (relay_number >= self.num_relays):
            raise Exception("LCUS relay board only has " + str(self.num_relays) + " relays")

        logger.info(f"activate relay number: {relay_number}")

        # every once and a while the relay does not change as commanded.
        # even if you limit on/off toggles to 1/sec - this makes me think this is
        # a bug in the cmd processing. so we'lljust command the same activate 3
        # times. this seems to make this issue go away
        self.__activate_relay(relay_number, True)
        self.__activate_relay(relay_number, True)
        self.__activate_relay(relay_number, True)

    def relay_deactivate(self, relay_number):
        if (relay_number >= self.num_relays):
            raise Exception("LCUS relay board only has " + str(self.num_relays) + " relays")

        logger.info(f"deactivate relay number: {relay_number}")

        # every once and a while the relay does not change as commanded.
        # even if you limit on/off toggles to 1/sec - this makes me think this is
        # a bug in the cmd processing. so we'lljust command the same deactivate 3
        # times. this seems to make this issue go away
        self.__activate_relay(relay_number, False)
        self.__activate_relay(relay_number, False)
        self.__activate_relay(relay_number, False)

