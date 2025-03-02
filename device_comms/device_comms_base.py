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
import queue
import re
from abc import ABC, abstractmethod
import logging
import time
from enum import Enum, auto
from typing import Union, List, Tuple

# Create a logging object with a null handler. if the caller of this class
# does not configure a logger context then no messages will be printed.
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

class StartupStatus(Enum):
    UNKNOWN = auto()
    SUCCESS = auto()
    ERROR = auto()

class SubprocessStartError(Exception):
    """Exception raised when a subprocess fails to start."""
    pass

class SubprocessShutdownError(Exception):
    """Exception raised when a subprocess fails to stop."""
    pass

class DeviceCommsBase(ABC):

    def __init__(self):

        self.write_queue = queue.Queue()
        self.read_queue = queue.Queue()

        self.is_logging = threading.Event()
        self.is_logging.clear()

        # guard any access to physical devices
        self.hardware_mutex = threading.BoundedSemaphore(1)

        # flag for async shutdown
        self.stop_requested = threading.Event()

        self.thread_mgmt_lock = threading.Lock()
        self.startup_status = StartupStatus.UNKNOWN

        self.hardware_recovery_time_sec = 0

    def __str__(self):
        return f"CommsDevice(isLogging:{self.is_logging.isSet()}. stop:{self.stop_requested.isSet()}"

    def set_event_map(self, event_map: dict) -> None:

        # make the event map bidirectional so we can get events from regex as well as regex for events
        # this requires that there are no duplicates of events or regexes
        try:
            self.trace_event_map = bidict.bidict( event_map )
        except ValueDuplicationError:
            raise Exception("Error initializing trace event map: you cannot have two of the same trace or two of the same event in the map")

    def acquire_hardware_mutex(self, timeout_ms = 10000) -> None:
        acquired = self.hardware_mutex.acquire( timeout = timeout_ms // 1000 )

        if not acquired:
            raise Exception("Debugger mutex unable to be acquired : " + str(self))

    def __timer_handler_release_hardware_mutex(self) -> None:
        self.hardware_mutex.release()

    def release_hardware_mutex(self) -> None:
        """ release the hardware mutex. if a recovery time is set, set a timer
            for this duration -> when the timer fires it will release the mutex.
            using a hardware recovery time is nice when a very short (e.g. <1 mS)
            restart of comms would cause stability issues. by starting a timer
            to release the mutex, you will not have to wait around for the
            recovery time unless you are explicitly reengaging with the hardware
            resource.
        """
        # if we have a recovery time after programming for stability reasons
        if (self.hardware_recovery_time_sec):

            self.debugger_release_timer = threading.Timer( self.hardware_recovery_time_sec,
                                                           self.__timer_handler_release_hardware_mutex)

            self.debugger_release_timer.start()
        else:
            self.hardware_mutex.release()

    def is_capturing_traces(self) -> bool:
        return self.is_logging.isSet()

    @abstractmethod
    def _start_capturing_traces(self, startup_complete_event: threading.Event) -> None:
        """ perform the steps to get logs out of your device. set the
            startup_complete_event as soon as logging is ready
        """
        raise NotImplementedError("Not yet implemented")

    @abstractmethod
    def _stop_capturing_traces(self) -> None:
        raise NotImplementedError("Not yet implemented")

    def start_capturing_traces(self) -> StartupStatus:
        """ start capturing the logs of a given device.
            return only once we have feedback that the hardware
            is in a good state
        """

        if self.is_logging.isSet():
            logger.info("Traces are already being captured. ignoring start request")
            return

        startup_complete_event = threading.Event()

        try:
            self._start_capturing_traces(startup_complete_event)

            # wait for the spawned thread to tell us it is completed successfully
            # before we return. this way you can assume that logs are processing
            # when this function returns
            startup_complete_event.wait()

        except Exception as e:
            logger.error(f"Log Startup Threw Exception: {e}")

        with self.thread_mgmt_lock:
            if self.startup_status != StartupStatus.SUCCESS:
                raise SubprocessStartError(f"Could not startup log capturing thread. status:{self.startup_status}")

        self.is_logging.set()

        return self.startup_status

    def stop_capturing_traces(self) -> None:
        """ stop capturing logs. this will stop all services running on your machine
            that interact with the debugger
            TODO: confirm if this allows accessories to go to sleep. it might require
                  a reset after logging is started before normal operation is resumed
        """

        if not self.is_logging.isSet():
            logger.info("Traces are not being captured. ignoring stop request")
            return

        self.stop_requested.set()

        try:
            self._stop_capturing_traces()
        except Exception as e:
            logger.error("Stop capturing traces exception: {e}")
            raise SubprocessShutdownError(f"Could not shutdown log capturing thread. error:{e}")

        self.is_logging.clear()

    def wait_for_event(self, required_events, avoided_events = None, timeout_ms = 10000, accumulate_traces = False, req_all_events = True):

        # event map must be set first
        if not self.event_map:
            return None

        #get the traces associated to a particular event
        required_traces = self.get_traces_for_events(required_events)

        avoided_traces = None
        if (avoided_events):
            avoided_traces = self.get_traces_for_events(avoided_events)

        (success, trace_match_list) = self.wait_for_trace( resp_req   = required_traces,
                                                           resp_avoid = avoided_traces,
                                                           timeout_ms = timeout_ms,
                                                           accumulate_traces = accumulate_traces,
                                                           req_all_responses = req_all_events)

        for trace_match in trace_match_list:
            print("trace match = " + str(trace_match))

            # get the event for the regex. it should always match an event
            event = self.trace_event_map.inverse.get(trace_match.regex, None)
            setattr(trace_match, "event", event)

        # return the status
        return (success, trace_match_list)

    # these are standardized events that you want to get the trace for.
    # a list of traces is returned
    def get_traces_for_events(self, events):

        traces = []

        if events and not isinstance(events, list):
            events = [events]

        for event in events:

            trace = self.trace_event_map.get(event, None)

            if (trace is None):
                raise Exception("No trace defined for event [" + str(event) + "]")

            traces.append(trace)

        if len(traces) == 0:
            return None

        return traces

    def __generate_trace_event(self, trace, regex, regex_match_obj):

        # always store the message that matched and the regex that was used
        trace_event = TraceEvent( trace = trace, regex = regex )

        # if there were named matches, store those in the struct as well
        if (regex_match_obj):
            for field, value in regex_match_obj.groupdict().items():
                setattr(trace_event, field, value)

        return trace_event

    def wait_for_trace(self,
                       resp_req: Union[str, List[str]] = None,
                       resp_avoid: Union[str, List[str]] = None,
                       timeout_ms: int = 10000,
                       run_to_completion: bool = False,
                       accumulate_traces: bool = False,
                       return_on_first_match: bool = False,
                       quiet: bool = False,
                       use_backlog: bool = True,
                       ) -> tuple([bool, str, List[str]]):
        """
        wait for a particular trace(s) to be seen.

        resp_req - string or list of strings to look for
        resp_avoid - string or list of strings that must not be seen. fail
                     immediately if seen
        timeout_ms - stop processing and fail if this duration has passed.
                     10 seconds by default. 0 == run forever
        run_to_completion - do not return when all of the traces have been
                            found. wait instead for the underlying process
                            to complete
        accumulate_traces - in the returned traces, by default we return the
                            last trace seen. set to True to return all traces
                            processed
        return_on_first_match - do we require all resp_req to be seen? default
                                yes. set to false to return when any are seen
        quiet - should we log the traces as they come ine. overrides logger settings
        use_backlog - by default we keep all traces in the read queue. set to
                      false to purge the read queue before processing any
                      traces

        returns tuple of:
               success
               traces seen
               list of resp_req that were not yet seen
        """

        # make sure resp_req is either None or a list
        if resp_req:
            if not isinstance(resp_req, list):
                resp_req = [resp_req]
            if len(resp_req) == 0:
                resp_req = None;

        # make sure resp_req is either None or a list
        if resp_avoid:
            if not isinstance(resp_avoid, list):
                resp_avoid = [resp_avoid]
            if len(resp_avoid) == 0:
                resp_avoid = None;

        # clear out any old traces
        if (not use_backlog):
            self.dump_traces()

        logger.debug("looking for traces: " +  str(resp_req))

        # make a helper function to get the time in milliseconds
        now = lambda: int(round(time.time() * 1000))
        start_time = now()
        traces_to_return = ''
        stop_processing = False

        try:

            while True:

                # check for timeout
                if (timeout_ms != 0 and (now() - start_time > timeout_ms)):
                    success = False
                    break

                if self.read_queue.empty():
                    # if we have no data sleep for a bit to not chew up the processor
                    time.sleep(0.001)
                else:
                    line = self.read_queue.get_nowait().strip()

                    if accumulate_traces:
                        traces_to_return += line + "\n"
                    else:
                        traces_to_return = line + "\n"

                    # print this to stdout
                    #if not quiet:
                    #    logger.debug(line)

                    # look through teh list of required responses. if we dont have
                    # any then just return
                    if (resp_req and len(resp_req)):

                        # if we found a required response, remove it from the list
                        for resp in resp_req:
                            # if this line matches one from the list then remove it
                            if re.search(resp, line, re.IGNORECASE):
                                resp_req.remove(resp)

                                if (return_on_first_match):
                                    logger.debug("Found a match. returning immediately")
                                    # no need to look at any more data
                                    stop_processing = True
                                    success = True
                                    break

                                # if we have no more responses we're looking for, just
                                # return
                                if (len(resp_req) == 0 and not run_to_completion):
                                    logger.debug("Found last required match")
                                    # no need to look at any more data
                                    stop_processing = True
                                    success = True
                                    break

                                # get more data so we can keep processing
                                continue

                    # we found everything we're looking for and are not letting
                    # the process self terminate
                    elif not run_to_completion:
                        logger.debug("Found all required traces")
                        # no need to look at any more data
                        stop_processing = True
                        success = True
                        break

                    if (resp_avoid and len(resp_avoid)):
                        # if we found a required response, remove it from the list
                        for resp in resp_avoid:
                            # if this line matches one from the list then remove it
                            if re.search(resp, line, re.IGNORECASE):
                                logger.debug("found response to avoid [" + line + "]")
                                # no need to look at any more data
                                stop_processing = True
                                success = False
                                break

                    if stop_processing:
                        break

        except Exception as e:
            print(f"Caught Exception: {e}")
            success = False

        logger.debug("Completed")

        return (success, traces_to_return.strip(), resp_req)

    # get rid of all logs in the trace_logs queue
    # return all the dumped logs in case you were interested
    def dump_traces(self):
        while not self.read_queue.empty():
            self.read_queue.get_nowait()

    # TODO: add support for binary cmds
    def send_cmd(self, cmd_str = None) -> bool:

        if (cmd_str == None):
            logger.error("cmd_str must be supplied")
            return False

        self.write_queue.put( cmd_str )

    def send_cmd_to_link_management(self, cmd) -> bool:
        """
        Enable sending commands to the lower level link management. Note this is
        different than the target device - this is intended to be able to send
        a message to the jlink server, websocket controller, etc

        returns true if message was sent successfully

        TODO: figure out what is needed for feedback. stdout? status enum?
        """
        logger.warn(f"Link management commands Not implemented for {self}")


