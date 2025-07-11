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
import logging
from enum import IntEnum
from EventGeneratorBase import *

# Create a logging object with a null handler. if the caller of this class
# does not configure a logger context then no messages will be printed.
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

class FunctionCaller(EventGeneratorBase):
    """
    Convenience class to be able to call arbitrary functions using the
    EventGenerator.
    """

    class SupportedEvents(IntEnum):
        FUNCTION_CALL = 0

    def __init__(self, function):
        """
        function - function to be called when events are being generated
        """

        ########################
        # check if the evt_gen_impl is a function or if it extends the EventGeneratorBase class
        ########################
        if (not callable(function)):
            raise Exception("function parameter must be a callable function")

        self.func = function

    def get_supported_events(self):
        """
        only supported event is a function call. function provided during
        initialization will be called from EventGenerator
        """

        supported_events = []

        # dynamically generate the list of supported events by looping through
        # the SupportedEvents class
        for event in FunctionCaller.SupportedEvents:
            supported_events.append(event)

        return supported_events

    def generate_event(self, event):

        if (event == FunctionCaller.SupportedEvents.FUNCTION_CALL):
            self.func(event)
        else:
            raise Exception("cannot generate event: " + str(event))

