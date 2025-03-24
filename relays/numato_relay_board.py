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
from enum import Enum, auto
from relay_base import RelayBase

# Create a logging object with a null handler. if the caller of this class
# does not configure a logger context then no messages will be printed.
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

class NumatoNode(Enum):
    relay = auto()
    gpio  = auto()
    adc   = auto()

class NumatoDevice(RelayBase):

    # number of channels represented in a hex char
    CHANNELS_PER_HEX_CHAR = 4

    """
    a utility class to simplify common functionality of numato products
    """
    def __init__(self, path, num_relays=0, num_gpio=0, num_adc=0):
        """
        if num_relays, num_gpio, or num_adc are given those values will be used. otherwise
        they will be autodiscovered
        """

        self.path = os.path.expanduser( os.path.abspath(path) )

        if not os.path.exists( self.path ):
            raise Exception("Could not open Relay path: " + str(path) )

        self.serial = serial.Serial( self.path, \
                                     baudrate=115200, \
                                     bytesize=8, \
                                     parity='N', \
                                     stopbits=1, \
                                     timeout=1 )

        self.num_gpio = 0
        self.num_adc = 0
        self.num_relays = 0

        autosense = (num_relays != 0) or (num_gpio != 0) or (num_adc != 0)

        super().__init__(num_relays, supports_autosense = autosense)

        # clear any remnants or partial info in usb or on target
        self._flush_buffers()

        self.fw_version = self.get_fw_version()
        self.id         = self.get_id()

        # overload anything autosensed
        if num_gpio != 0:
            self.num_gpio = num_gpio

        if num_adc != 0:
            self.num_adc = num_adc

        if num_relays != 0:
            self.num_relays = num_relays

    def _flush_buffers(self):
        with self._lock:
            self.serial.flushInput()
            self.serial.flushOutput()

        #send an empty command to clear the buffers on the target
        self._execute_serial_cmd('')

    def _execute_serial_cmd(self, cmd):

        response = ''

        with self._lock:
            logger.debug("sending: " + cmd)
            self.serial.write( str.encode(cmd + "\r") )

            # read the echo'd cmd we just sent
            response = self.serial.read_until(expected=b'\r')

            # read the response and strip off the cruft
            response = self.serial.read_until(expected=b'>').lstrip().rstrip(b'\r\n>').decode("ascii")

            logger.debug("response = [" + response + "]")

        if (response == ''):
            response = None

        return response

    def _create_channel_num_list_from_mask(self, on_mask, max_channels):
        """
        given a mask, turn it into a list of channels that are enabled
        """

        on_channels = []

        if (isinstance(on_mask, str)):
            on_mask = int(on_mask, 0)

        # make a copy of the on_mask var that we can edit
        mask = on_mask
        # keep a counter corresponding to the channel we're currently
        # evaluating
        curr_channel_num = 0

        # run until the rest of the channels are off, or we've exceeded the max number
        # of channels on our part
        while(mask != 0 and curr_channel_num < max_channels):

            currbit = mask & 0x1

            # add current channel number to list of on channels if bit in mask is set
            if (currbit):
                on_channels.append(curr_channel_num)
                #logger.debug("channel " + str(curr_channel_num) + " is on")

            # update mask and channel count
            mask = mask >> 1
            curr_channel_num += 1

        #logger.debug("mask " + str(on_mask) + " = " + str(on_channels))
        #logger.debug('returning after ' + str(curr_channel_num))
        return on_channels

    def _create_mask_from_channel_num_list(self, on_channels, max_channels):
        mask = 0
        logger.debug("on chan: " + str(on_channels))

        # sort the list
        on_channels.sort()

        for i in on_channels:
            # if we're given an index that is outside of the bounds of the
            # mask then return
            if (i >= max_channels):
                raise Exception("channel " + str(i) + " is not valid. " + str(max_channels - 1) + " is max value possible for this numato board")

            mask |= (1 << (i))

        #logger.debug("final mask: " + hex(mask))
        return mask

    def _get_max_channels_for_channel_node(self, channel_node):

        max_channels = { NumatoNode.gpio : self.num_gpio,
                         NumatoNode.relay : self.num_relays,
                         NumatoNode.adc : self.num_adc}.get(channel_node, 0)

        return max_channels

    def _map_channel_num_to_alpha(self, channel_num, max_channels):
        """
        Numato counts 0-9 then a-v, in the case of 32 port boards.
        in the case of 64 channel devices they count up based on number so no translation.
        - this is true of relay boards. need to confirm on gpio, etc
        """

        # if our channel number is less than or equal to 9 then all boards use numbers
        # if we have 64 channels on the board then we also always use numbers
        if (channel_num <= 9 or max_channels >= 64):
            return channel_num

        # if we have 32 or less channels onboard and we want to address channel number 10+
        # then we need to convert to a letter where 10+ maps to a-v... note its not hex.
        else:
            # chr maps number to an ascii character. 97 is a, 98 is b, and so on
            # so 10 + x = a, where a is 97 by definition -> x == 87. that's our offset
            return chr(channel_num + 87)

    def _determine_mask_width_from_max_channels(self, max_channels):
        # number of characters numato boards suspect is dependent on how
        # many ports there are. up to 8 port boards, for instance, will only
        # take 00-ff as the mask value. 16 port boards need 4 hex chars, etc
        mask_chars = "02"
        if max_channels >= 64:
            mask_chars = "016"
        elif max_channels >= 32:
            mask_chars = "08"
        elif max_channels >= 16:
            mask_chars = "04"

        return mask_chars

    def writeall(self, channel_node = NumatoNode.relay, on_channels = []):
        """
        channel_node - one of 'relay', 'gpio'
        on channels - list of integer channels that should be enabled. start counting at 0
                      all other channels will be disabled
        """

        if not isinstance(channel_node, NumatoNode):
            raise Exception("Invalid channel node")

        max_channels = self._get_max_channels_for_channel_node(channel_node)

        mask_value = self._create_mask_from_channel_num_list(on_channels,
                                                              max_channels)

        mask_chars = self._determine_mask_width_from_max_channels(max_channels)

        mask = ('{:' + mask_chars + 'x}').format(mask_value)

        response = self._execute_serial_cmd(channel_node.name + " writeall " + mask)

        return response

    def readall(self, channel_node):
        """
        channel_node - one of 'relay', 'gpio'

        returns a list of all channels that are in the 'on' state. whatever that means
                for the given channel type
        """

        if not isinstance(channel_node, NumatoNode):
            raise Exception("Invalid channel node")

        on_mask = int(self._execute_serial_cmd(channel_node.name + " readall"), 16)

        max_channels = self._get_max_channels_for_channel_node(channel_node)

        on_channels = self._create_channel_num_list_from_mask(on_mask, max_channels)

        return on_channels

    def get_fw_version(self):
        version = self._execute_serial_cmd("ver")

        return version

    def get_id(self):
        module_id = self._execute_serial_cmd("id get")

        return module_id

    def set_id(self, new_id):
        module_id = self._execute_serial_cmd('set id ' + str(new_id))
        return module_id

    def set(self, channel_node, channel_number):
        """
        channel_node - one of gpio, relay
        channel_number - integer value corresponding to channel to activate
        """
        if not isinstance(channel_node, NumatoNode):
            raise Exception("Invalid channel node")

        set_cmd = 'set'
        if channel_node == NumatoNode.relay:
            set_cmd = 'on'

        max_channels = self._get_max_channels_for_channel_node(channel_node)

        channel = self._map_channel_num_to_alpha(channel_number, max_channels)

        cmd = '{:s} {:s} {:s}'.format(channel_node.name, set_cmd, str(channel))

        return self._execute_serial_cmd(cmd)

    def clear(self, channel_node, channel_number):
        if not isinstance(channel_node, NumatoNode):
            raise Exception("Invalid channel node")

        clear_cmd = 'clear'
        if channel_node == NumatoNode.relay:
            clear_cmd = 'off'

        max_channels = self._get_max_channels_for_channel_node(channel_node)

        channel = self._map_channel_num_to_alpha(channel_number, max_channels)

        cmd = '{:s} {:s} {:s}'.format(channel_node.name, clear_cmd, str(channel))

        return self._execute_serial_cmd(cmd)

    def is_set(self, channel_node, channel_number):
        '''
        same as read, but for boolean logic, return a boolean
        '''

        if not isinstance(channel_node, NumatoNode):
            raise Exception("Invalid channel node")

        is_set = None

        max_channels = self._get_max_channels_for_channel_node(channel_node)

        channel = self._map_channel_num_to_alpha(channel_number, max_channels)

        response = self.read(channel_node, channel)

        # map response to logical boolean
        if (response == '1' or response == 'on'):
            is_set = True
        elif (response == '0' or response == 'off'):
            is_set = False
        else:
            is_set = None

        return is_set

    def read(self, channel_node, channel_number):
        """
        create a read command for a given channel.

        channel_node - one of 'adc', 'gpio', 'relay'
        channel_number - which instance of that channel is being read
        """

        if not isinstance(channel_node, NumatoNode):
            raise Exception("Invalid channel node")

        max_channels = self._get_max_channels_for_channel_node(channel_node)

        channel = self._map_channel_num_to_alpha(channel_number, max_channels)

        value = self._execute_serial_cmd(channel_node.name + ' read ' + str(channel))

        if (value == ''):
            value = None

        return value

    def activate_relay(self, relay_num):
        """
        Convenience function
        """
        with self._lock:
            self.set(NumatoNode.relay, relay_num)
            self._relay_status[ relay_num ] = 1

    def deactivate_relay(self, relay_num):
        """
        Convenience function
        """
        with self._lock:
            self.clear(NumatoNode.relay, relay_num)
            self._relay_status[ relay_num ] = 0

    def toggle_relay(self, relay_num):
        """
        Convenience function
        """
        if self.is_set(NumatoNode.relay, relay_num):
            self.activate_relay( relay_num )
        else:
            self.deactivate_relay( relay_num )

    def write_all_relays(self, activated_relays):
        """
        Convenience function
        """
        self.writeall( channel_node = NumatoNode.relay,
                       on_channels = activated_relays )

        # keep _relay_status up to date
        for i in range(0, self.num_relays):
            if i in activated_relays:
                self._relay_status[i] = 1
            else:
                self._relay_status[i] = 0

    def read_all_relays(self):
        """
        Convenience function
        """
        return self.readall( channel_node = NumatoNode.relay )

    def set_iodir(self, channel_node, input_channels):

        # create a mask value with 1's corresponding to input channels
        mask_value = self.device._create_mask_from_channel_num_list(input_channels, self.num_gpio)

        # determine how many chars to print based on the max number of channels
        mask_chars = self.device._determine_mask_width_from_num_channels(self.num_gpio)

        # create the actual mask to send to the numato board. it's very particular
        mask = ('{:' + mask_chars + 'x}').format(mask_value)

        #actually execute the cmd
        return self.device._execute_serial_cmd(channel_node.name + ' iodir ' + mask)

    def setmask(self, channel_node, mask):

        if not isinstance(channel_node, NumatoNode):
            raise Exception("Invalid channel node")

        max_channels = self._get_max_channels_for_channel_node(channel_node)

        if (len(mask) * NumatoDevice.CHANNELS_PER_HEX_CHAR > max_channel):
            raise Exception("mask is greater than available channels")

        value = self._execute_serial_cmd(channel_node.name + ' iomask ' + mask)

        if (value == ''):
            value = None

        return value

    def autosense_hardware(self):
        self.auto_discover_channels( discover_gpio = True,
                                     discover_relays = True,
                                     discover_adc = True)

    def auto_discover_channels(self, discover_gpio=False, discover_adc=False, discover_relays=False) -> None:
        """
        " if you ask to read a gpio/adc/relay that is beyond the number available,
        " numato returns nothing. We can use this information to determine the
        " number of each node type that is present.
        "
        " It is suggested that you use this in a setup wizard or similar tool
        " to generate a config file but do not rely on this for each test run
        " since this behavior may change in the future
        """

        #############################
        #discover num gpio
        #############################
        if (discover_gpio):
            num_gpio = 0

            max_gpio = 128

            # some of the modules respond to commands to read
            # gpio beyond the number available. this is a way
            # to limit better
            on_mask = self._execute_serial_cmd("gpio readall")
            if (on_mask):
                max_gpio = len(on_mask) * NumatoDevice.CHANNELS_PER_HEX_CHAR

            for i in range(0,max_gpio):
                resp = self.is_set(NumatoNode.gpio, i)
                if resp is None:
                    break
                num_gpio = i + 1

            logger.info(f"auto discovered {num_gpio} gpio")
            self.num_gpio = num_gpio

        #############################
        #discover num relays
        #############################
        if (discover_relays):
            max_relays = 128
            num_relays = 0

            on_mask = self._execute_serial_cmd("relay readall")
            if (on_mask):
                max_relays = len(on_mask) * NumatoDevice.CHANNELS_PER_HEX_CHAR

            for i in range(0, max_relays):
                self.num_relays = i
                resp = self.read(NumatoNode.relay, i)
                if resp is None:
                    break
                num_relays = i + 1

            logger.info(f"auto discovered {num_relays} relays")
            self.num_relays = num_relays

        #############################
        #discover num adc
        #############################
        if (discover_adc):
            num_adc = 0
            # we will never have more adc's than gpio
            max_adc = self.num_gpio
            for i in range(0,max_adc):
                resp = self.read(NumatoNode.adc, i)
                if resp is None:
                    break
                num_adc = i + 1

            logger.info(f"auto discovered {num_adc} adcs")
            self.num_adc = num_adc

