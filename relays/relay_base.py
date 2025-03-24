import os
from abc import ABC, abstractmethod
import threading
import logging

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)

class RelayBase(ABC):

    def __init__(self, num_relays, supports_autosense:bool = False):

        self.num_relays = num_relays

        # recursive lock for hardware access
        self._lock = threading.RLock()

        # if the relay board that extends this class does not have a read
        # command to get current status, then care must be taken to keep
        # _relay_status up to date as commands are executed.
        # for now, we just keep this struct with keys of the relay number,
        # and the value is 1 for activated and 0 for deactivated
        self._relay_status = {}

        if supports_autosense:
            self.autosense_hardware()

        # if needed
        self._flush_buffers()

        # turn off all relays
        self.write_all_relays([])

        # initialize relay_status dictionary
        for i in range(0, num_relays):
            self._relay_status[i] = 0

    @abstractmethod
    def activate_relay(self, relay_number:int) -> None:
        """
        be sure to:
            1. set self._relay_status[ relay_number ] = 1
            2. utilize the self._lock when accessing hardware
        """
        pass

    @abstractmethod
    def deactivate_relay(self, relay_number:int) -> None:
        """
        be sure to:
            1. set self._relay_status[ relay_number ] = 0
            2. utilize the self._lock when accessing hardware
        """
        pass

    def _flush_buffers(self) -> None:
        """
        overload this if you want to make sure your device is ready to
        receive the first cmd. useful to send a \n when dealing with a
        cli interface. you may have garbage in the buffer already
        """
        pass

    def autosense_hardware(self) -> None:
        """
        overload this if you want to insert logic for autosensing hardware
        capabilities on instantiation
        """
        pass

    def toggle_relay(self, relay_number:int) -> None:
        if self.is_relay_active( relay_number ):
            self.deactivate_relay( relay_number )
        else:
            self.activate_relay( relay_number )

    def write_all_relays(self, on_channels:list[int]) -> None:
        """
        on channels - list of integer channels that should be enabled. start counting at 0
                      all other channels will be disabled
        overload this if the relay board has a multiread command
        """

        for channel in range(0, self.num_relays):
            if (channel in on_channels):
                self.relay_activate(channel)
            else:
                self.relay_deactivate(channel)

    def read_all_relays(self) -> list[int]:
        """
        read and return a list of all channels that are enabled
        returns a list of relay numbers as int representing all activated relays
        overload this if the relay board has a multiread command
        """
        on_channels = []

        # loop through each channel and see if it is active. build a list
        # out of these statuses
        for channel in range(0, self.num_relays):
            if (self.is_relay_active(channel)):
                on_channels.append(channel)

        return on_channels

    def is_relay_active(self, relay_number):
        """
            not every relay board has a read function. by default we relay on
            the cached state of the relay though boards that support relay read
            functionality should overload this function
            overload this if the relay board has a read command
        """
        if (relay_number >= self.num_relays):
            raise Exception("Relay board only has " + str(self.num_relays) + " relays")

        return (self._relay_status[relay_number] == 1)

