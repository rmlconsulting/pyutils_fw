
import pprint
import logging
import os
import sys
import time
import signal
import traceback
from enum import Enum, auto

# add parent directory to python path for this example
this_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.abspath(os.path.join(this_dir, '..'))
sys.path.insert(0, parent_dir)

import jlink_device
from device_comms_base import TraceResponseFormat, DeviceTraceCollectPattern

##########################################
# LOGGING
##########################################
# for lots of logging uncomment this block
logging.basicConfig(
    level=logging.DEBUG,
#    #format="%(asctime)s-%(name)s-%(levelname)s:%(message)s"
)

# for logging in this file, uncomment this block
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())
logger.setLevel(logging.DEBUG)

##########################################
# device setup
##########################################
# some example device configs
#config = jlink_device.JLinkTransportConfig( "NRF52832_XXAA" )
config = jlink_device.JLinkTransportConfig( "STM32G491VE", speed=5000 )

device = jlink_device.JLinkDevice(config)

##########################################
# Handle ctrl-c
##########################################
#TODO: wait for trace and other high level functions need to monitor shutdown
#      requests as well
#def handle_sigint(signum, frame):
#    print("Received SIGINT (Ctrl+C)! Exiting gracefully.")
#    device.stop_capturing_traces()
#
#    sys.exit(0)
#
#signal.signal(signal.SIGINT, handle_sigint)

##########################################
# run test
##########################################

class Events(Enum):
    BUTTON_PRESS = auto()
    BUTTON_RELEASE = auto()
    BOGUS_EVENT = auto()

global_event_map = {
                       Events.BUTTON_PRESS : r"Button (?P<button_num>\d+) pressed",
                       Events.BUTTON_RELEASE : r"Button (?P<button_num>\d+) released",
                       Events.BOGUS_EVENT : r"SomeTraceThatWillNeverBeProduced",
                    }

device.set_event_map(global_event_map)

############ Test 1: wait for all events. processed responses ##################
print("\n\n#### TEST 1 : wait for 2 events. return processed logs ######")

try:
    events = [Events.BUTTON_PRESS, Events.BUTTON_RELEASE]

    print("press and release a button in the next 5 seconds")
    success, traces, remaining_search = device.wait_for_event(required_events = events,
                                                              timeout_ms = 5000,
                                                              return_on_first_match = False,
                                                              trace_collect_pattern = DeviceTraceCollectPattern.MATCHING,
                                                              trace_response_format = TraceResponseFormat.PROCESSED_RESPONSES)

    print(f"Setup: {events}\n")
    print(f"Results: success:{success}. remaining:{remaining_search}. traces:")
    pprint.pprint(traces)

    print("running checks...")
    assert success, "Test unexpectedly failed"
    assert isinstance(traces, list) and all(isinstance(trace, dict) for trace in traces), "traces is the wrong type"
    assert len(traces) == len(events), "unexpected number of returned events"
    assert len(remaining_search) == 0, "Remaining events should be emtpy"
except Exception as e:
    print(e)
    traceback.print_exc()
    print("\n\n#### TEST 1: FAILED ######")
else:
    print("\n\n#### TEST 1: PASSED ######")

############ Test 2: wait for all events. raw ##################
device.dump_traces()
print("\n\n#### TEST 2 : wait for 2 events. return raw logs ######")

try:
    events = [Events.BUTTON_PRESS, Events.BUTTON_RELEASE]

    print("press and release a button in the next 5 seconds")
    success, traces, remaining_search = device.wait_for_event(required_events = events,
                                                              timeout_ms = 5000,
                                                              # wipe any logs from the last test
                                                              use_backlog = False,
                                                              trace_collect_pattern = DeviceTraceCollectPattern.MATCHING,
                                                              trace_response_format = TraceResponseFormat.RAW_TRACES)

    print(f"Setup: {events}")
    print(f"Results: success:{success}. remaining:{remaining_search}. traces:\n{traces}")

    print("running checks...")
    assert success, "Test unexpectedly failed"
    assert isinstance(traces, str), "traces is the wrong type"
    assert len(traces) > 0, "traces is empty?"
    assert len(remaining_search) == 0, "Remaining events should be emtpy"
except Exception as e:
    print(e)
    traceback.print_exc()
    print("\n\n#### TEST 2: FAILED ######")
else:
    print("\n\n#### TEST 2: PASSED ######")

############ Test 3: return on first event. check processed logs ##################
device.dump_traces()
print("\n\n#### TEST 3 ######")

try:
    events = [Events.BUTTON_PRESS, Events.BUTTON_RELEASE]

    print(f"Setup: {events}")

    print("press and release a button in the next 5 seconds")
    # get all events, just one at a time
    while len(events) > 0:

        # update events with the remaining events
        success, traces, events = device.wait_for_event( required_events = events,
                                                         timeout_ms = 5000,
                                                         return_on_first_match = True,
                                                         # wipe any logs from the last test
                                                         use_backlog = False,
                                                         trace_response_format = TraceResponseFormat.PROCESSED_RESPONSES)

        print(f"## Partial Results: success:{success}. remaining:{events}. traces:")
        pprint.pprint(traces)
        assert success, "Test unexpectedly failed"

    print("running checks...")
    assert isinstance(traces, list) and all(isinstance(trace, dict) for trace in traces), "traces is the wrong type"
    assert len(traces) > 0, "traces is empty?"
    assert len(events) == 0, "Remaining events should be emtpy"
except Exception as e:
    print(e)
    traceback.print_exc()
    print("\n\n#### TEST 3: FAILED ######")
else:
    print("\n\n#### TEST 3: PASSED ######")

############ Test 4: return on first event. check raw logs ##################
device.dump_traces()
print("\n\n#### TEST 4 ######")

try:
    events = [Events.BUTTON_PRESS, Events.BUTTON_RELEASE]

    print(f"Setup: {events}")

    print("press and release a button in the next 5 seconds")
    # get all events, just one at a time
    while len(events) > 0:

        # update events with the remaining events
        success, traces, events = device.wait_for_event( required_events = events,
                                                         timeout_ms = 5000,
                                                         return_on_first_match = True,
                                                         # wipe any logs from the last test
                                                         use_backlog = False,
                                                         trace_collect_pattern = DeviceTraceCollectPattern.ALL,
                                                         trace_response_format = TraceResponseFormat.RAW_TRACES)

        print(f"## Partial Results: success:{success}. remaining:{events}. traces:")
        pprint.pprint(traces)
        assert success, "Test unexpectedly failed"

    print("running checks...")
    assert isinstance(traces, str), "traces is the wrong type"
    assert len(traces) > 0, "traces is empty?"
    assert len(events) == 0, "Remaining events should be emtpy"
except Exception as e:
    print(e)
    traceback.print_exc()
    print("\n\n#### TEST 4: FAILED ######")
else:
    print("\n\n#### TEST 4: PASSED ######")

print("\n\n#### TEST 5: test for logs entering before wait_for_xxxx calls ######")

try:
    events = [Events.BUTTON_PRESS, Events.BUTTON_RELEASE]

    print(f"Setup: {events}")
    # manually dump any traces hanging around
    device.dump_traces()
    print("Press and release a button in the next 5 seconds")
    time.sleep(5)
    print("Do not press anything")
    time.sleep(1)
    success, traces, remaining_traces = device.wait_for_event( required_events = events,
                                                               timeout_ms = 500,
                                                               return_on_first_match = True,
                                                               # wipe any logs from the last test
                                                               use_backlog = False,
                                                               trace_collect_pattern = DeviceTraceCollectPattern.MATCHING,
                                                               trace_response_format = TraceResponseFormat.RAW_TRACES)

    print(f"Results: success:{success}. remaining:{remaining_search}. traces:\n{traces}")
    print("running checks...")
    # we should not have matched the button presses from before
    assert success == False
    assert isinstance(traces, str), "traces is the wrong type. expected str"
    assert len(traces) == 0, "traces should be empty"
    assert len(remaining_traces) == len(events), "Remaining events len must equal events len"
except Exception as e:
    print(e)
    traceback.print_exc()
    print("\n\n#### TEST 5: FAILED ######")
else:
    print("\n\n#### TEST 5: PASSED ######")

print("\n\n#### TEST 6: test for logs entering before wait_for_xxxx calls ######")
device.dump_traces()
try:
    # only look for release. we expect to get a button press event that will
    # be returned without any associate _event or _regex_search_string fields set
    events = [Events.BUTTON_RELEASE]

    print(f"Setup: {events}")
    # manually dump any traces hanging around
    device.dump_traces()
    print("Press and release a button in the next 5 seconds")
    time.sleep(5)
    success, traces, remaining_traces = device.wait_for_event( required_events = events,
                                                               # short duration wait
                                                               timeout_ms = 50,
                                                               return_on_first_match = True,
                                                               # use any logs from the last test
                                                               use_backlog = True,
                                                               trace_collect_pattern = DeviceTraceCollectPattern.ALL,
                                                               trace_response_format = TraceResponseFormat.PROCESSED_RESPONSES)

    print(f"Results: success:{success}. remaining:{remaining_search}. traces:\n{traces}")
    print("running checks...")
    # we should not have matched the button presses from before
    assert success
    assert isinstance(traces, list) and all(isinstance(trace, dict) for trace in traces), "traces is the wrong type"
    # we should have at least 1 message that does not have a regex search string
    assert any(trace['_regex_search_string'] == None for trace in traces)
    # we should have at least 1 message that does have a regex search string
    assert any(trace['_regex_search_string'] is not None for trace in traces)
    assert len(traces) > 0, "traces should not be empty"
    assert len(remaining_traces) == 0, "Remaining events len must equal events len"
except Exception as e:
    print(e)
    traceback.print_exc()
    print("\n\n#### TEST 6: FAILED ######")
else:
    print("\n\n#### TEST 6: PASSED ######")


print("\n\n#### TEST 7: Test new connection pressure test ######")

try:
    print("XXXXXXX stop XXXXXXXX")
    device.stop_capturing_traces()
    print("XXXXXXX start XXXXXXXX")
    device.start_capturing_traces()
    print("XXXXXXX stop XXXXXXXX")
    device.stop_capturing_traces()
    print("XXXXXXX start XXXXXXXX")
    device.start_capturing_traces()
    print("XXXXXXX stop XXXXXXXX")
    device.stop_capturing_traces()
    print("XXXXXXX start XXXXXXXX")
    device.start_capturing_traces()
except Exception as e:
    print(e)
    traceback.print_exc()
    print("\n\n#### TEST 7: FAILED ######")
else:
    print("\n\n#### TEST 7: PASSED ######")

print("\n\n#### TEST 8: Test timeouts ######")
try:
    timeout_s = 1
    print(f"please wait {timeout_s} seconds")

    start_time = time.time()
    success, traces, remaining_traces = device.wait_for_event( required_events = [Events.BOGUS_EVENT],
                                                               # short duration wait
                                                               timeout_ms = timeout_s * 1000,
                                                               # use any logs from the last test
                                                               use_backlog = False,
                                                               trace_collect_pattern = DeviceTraceCollectPattern.ALL,
                                                               trace_response_format = TraceResponseFormat.PROCESSED_RESPONSES)
    end_time = time.time()
    elapsed_time_s = time.time() - start_time

    print(f"Results: success:{success}. remaining:{remaining_search}. duration:{elapsed_time_s:.2f} traces:\n{traces}")
    print("running checks...")
    # we should not have matched the button presses from before
    assert success == False, "Expected a failure on button press/release event"
    # make sure the elapsted time was withing 10% of the timeout_ms
    assert elapsed_time_s >= timeout_s * 0.9
    assert elapsed_time_s <= timeout_s * 1.1
    assert isinstance(traces, list) and all(isinstance(trace, dict) for trace in traces), "traces is the wrong type"
    # we should have at least 1 message that does not have a regex search string
    assert not any(trace['_regex_search_string'] is not None for trace in traces)
    assert len(remaining_traces) == len(events), "Remaining events len must equal events len"
except Exception as e:
    print(e)
    traceback.print_exc()
    print("\n\n#### TEST 8: FAILED ######")
else:
    print("\n\n#### TEST 8: PASSED ######")


print("\n\n#### TEST 9: Test avoided events ######")
try:
    # only look for release. we expect to get a button press event that will
    # be returned without any associate _event or _regex_search_string fields set
    events = [Events.BUTTON_RELEASE, Events.BUTTON_PRESS]
    bogus_events = [Events.BOGUS_EVENT]

    print("Press and release a button in the next 5 seconds")
    success, traces, remaining_traces = device.wait_for_event( required_events = bogus_events,
                                                               # avoid button presses to cause it to fail intentionally
                                                               avoided_events = events,
                                                               # short duration wait
                                                               timeout_ms = 5000,
                                                               # use any logs from the last test
                                                               use_backlog = False,
                                                               trace_collect_pattern = DeviceTraceCollectPattern.MATCHING,
                                                               trace_response_format = TraceResponseFormat.PROCESSED_RESPONSES)

    print(f"Results: success:{success}. remaining:{remaining_search}. traces:\n{traces}")
    print("running checks...")
    # we should not have matched the button presses from before
    assert success == False, "Expected a failure on button press/release event"
    assert isinstance(traces, list) and all(isinstance(trace, dict) for trace in traces), "traces is the wrong type"
    assert all(trace['_regex_search_string'] is not None for trace in traces)
    # we should get a trace that matches an avoided event
    assert len(traces) >= 0, "traces should not be empty"
    assert len(remaining_traces) == len(bogus_events), "Remaining events len must equal events len"
except Exception as e:
    print(e)
    traceback.print_exc()
    print("\n\n#### TEST 9: FAILED ######")
else:
    print("\n\n#### TEST 9: PASSED ######")

print("still left to test...")
print("  - return values for all, matching, etc")

##########################################
# shutdown
##########################################
device.stop_capturing_traces()

