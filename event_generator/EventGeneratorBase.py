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

import pytest
import sys
import os
import threading
import re
import time
import random
import logging
from abc import ABC, abstractmethod
from enum import IntEnum
from typing import NamedTuple
from dataclasses import dataclass

# Create a logging object with a null handler. if the caller of this class
# does not configure a logger context then no messages will be printed.
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

class IntervalType(IntEnum):
    INTERVAL_FIXED  = 0
    INTERVAL_RANDOM = 1

class EventGeneratorBase(ABC):

    @abstractmethod
    def generate_event(self, event):
        """
        take action for the desired event
        """
        raise Exception("Not yet implemented")

    @abstractmethod
    def get_supported_events(self):
        """
        this should return a list of events that can be triggered
        """
        pass
        raise Exception("Not yet implemented")

@dataclass
class EventTiming:
    # specify the type of time interval, fixed vs random
    time_interval_type : IntervalType
    random_interval_min_ms: int = 0
    random_interval_max_ms: int = 10000
    fixed_interval_time_ms: int = 0

    # true = continous events. false = one shot
    is_repeated: bool = True

    # specify the max time in which events should be generated
    timeout_ms: int = 0

class EventCoordinator():

    def __init__(self, evt_gen_impl, evt_list, timing_config, max_events=0, evt_gen_signal=None):
        """
        evt_gen_impl - an object that extends EventGeneratorBase

        evt_list     - list of events to be generated. the event generator will
                       repeatedly iterate over the list in the given order on the

        timing_config - specifies the event generation timing parameters

        max_events - max number of events to generate after calling start. set to 0
                     to indicate no maximum

        evt_gen_signal - user supplied event to be set to signal that an event
                         has tripped

        """

        ########################
        # check if the evt_gen_impl is a function or if it extends the EventGeneratorBase class
        ########################
        if (evt_gen_impl is None):
            raise Exception("Event generator requires evt_gen_impl to be a an object that extends EventGeneratorBase")

        if (not issubclass(type(evt_gen_impl), EventGeneratorBase)):
            raise Exception("evt_gen_impl param should be a class which extends EventGeneratorBase")

        ########################
        # do we have a valid event list
        ########################
        if (evt_list is None):
            raise Exception("Event generator requires a list of events to generate")

        # make sure the events to generate are in the list of supported events
        supported_events = evt_gen_impl.get_supported_events()
        for event in evt_list:
            if event not in supported_events:
                raise Exception("Event in evt_list not supported. supported events = " + str(supported_events))

        # update the random module's seed based on system time
        random.seed()

        # store user params
        self.evt_gen_impl = evt_gen_impl
        self.timing_config = timing_config
        self.evt_list = evt_list
        self.evt_gen_signal = evt_gen_signal
        self.max_events = max_events

        self._timer_mutex = threading.RLock()
        self._event_count = 0
        self._timer = None
        self._start_time_ms = 0
        self._is_running = False

    def _generate_next_event(self):
        """
        iterate over the list of events in the list
        """

        # use the overall counter to determine the next index in the evt_list
        event_idx = self._event_count % len(self.evt_list)
        evt = self.evt_list[ event_idx ]

        # invoke the actual event generation logic
        self.evt_gen_impl.generate_event(evt)

        self._event_count += 1

        # if we were supplied a threading event to give notice when the
        # event occurs then call it here
        if (self.evt_gen_signal):
            self.evt_gen_signal.set()

        # start the timer again if we're not a oneshot timer
        if (self.timing_config.is_repeated):
            self._start_timer()

    def _start_timer(self):
        """
        start generating events
        """

        logger.debug('starting timer')

        # determine time base
        timer_duration = 0
        stop = False

        now_ms = lambda: round(time.time() * 1000)

        #make sure we don't go over max limit of events
        if (self.timing_config.time_interval_type == IntervalType.INTERVAL_FIXED):
            timer_duration = self.timing_config.fixed_interval_time_ms

        elif (self.timing_config.time_interval_type == IntervalType.INTERVAL_RANDOM):
            timer_duration = random.randint( self.timing_config.random_interval_min_ms, \
                                             self.timing_config.random_interval_max_ms)

        logger.debug("eg timer duration = " + str(timer_duration))

        #make sure we don't go over max limit of events
        if (self.max_events != 0 and self._event_count >= self.max_events):
            stop = True

        # make sure we're not going to generate an event beyond the timeout
        elif self.timing_config.timeout_ms != 0 and \
             ((now_ms() + timer_duration) - self._start_time_ms >= self.timing_config.timeout_ms):
            stop = True

        # stop execution or start the next timer per timing requirements
        if (stop):
            self.stop()
        else:

            # need a mutex here in case the stop function is called between cancel and
            # defining the new thread
            with self._timer_mutex:
                # if we have a timer running cancel it
                if (self._timer and self._timer.is_alive()):
                    self._timer.cancel()

                self._timer = threading.Timer( timer_duration / 1000, self._generate_next_event)
                self._timer.start()

    def start(self):

        if (self._is_running):
            logger.debug("ignoring duplicate start request")
            return

        self._is_running = True
        now_ms = lambda: round(time.time() * 1000)

        self._start_time_ms = now_ms()

        self._start_timer()

    def stop(self):
        """
        stop generating events
        """
        with self._timer_mutex:
            if (self._timer.is_alive()):
                self._timer.cancel()

            self._timer = None

        self._is_running = False

    def is_running(self):
        return self._is_running

