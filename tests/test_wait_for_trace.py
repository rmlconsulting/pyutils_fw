"""wait_for_trace / wait_for_event matching semantics, no hardware.

FakeComms is a minimal concrete DeviceCommsBase: traces are fed straight
into read_queue. Timeouts are kept in the tens of milliseconds so the
whole file runs in well under a second.
"""

import enum

import pytest

from pyutils_fw.device_comms import (
    DeviceCommsBase,
    DeviceTraceCollectPattern,
    StartupStatus,
    TraceResponseFormat,
)


class FakeComms(DeviceCommsBase):
    def __init__(self):
        super().__init__(name="fake", hardware_recovery_time_sec=0)

    def _start_capturing_traces(self, startup_complete_event):
        with self._thread_mgmt_lock:
            self._startup_status = StartupStatus.SUCCESS
        startup_complete_event.set()

    def _stop_capturing_traces(self):
        pass

    def _send_cmd_to_link_management(self, cmd):
        pass


class Events(enum.Enum):
    PING = enum.auto()
    BOOT = enum.auto()
    CRASH = enum.auto()


@pytest.fixture
def comms():
    device = FakeComms()
    device.start_capturing_traces()
    return device


# ---------------------------------------------------------------- required

def test_single_required_string(comms):
    comms.read_queue.put("hello world")
    success, traces, remaining = comms.wait_for_trace("hello", timeout_ms=200)
    assert success is True
    assert remaining == []
    assert "hello world" in traces


def test_caller_list_is_not_mutated(comms):
    # regression: wait_for_trace consumed the caller's list
    wanted = ["alpha", "beta"]
    comms.read_queue.put("alpha here")
    comms.read_queue.put("beta here")

    success, traces, remaining = comms.wait_for_trace(wanted, timeout_ms=300)

    assert success is True
    assert remaining == []
    assert wanted == ["alpha", "beta"]


def test_one_line_matching_two_patterns(comms):
    # regression: removing from the list being iterated skipped the entry
    # after every match, so the second pattern was never checked
    comms.read_queue.put("alphabet soup")
    success, traces, remaining = comms.wait_for_trace(
        [r"alpha", r"alph"], timeout_ms=300)
    assert success is True
    assert remaining == []


def test_timeout_returns_remaining(comms):
    comms.read_queue.put("nothing relevant")
    success, traces, remaining = comms.wait_for_trace(
        ["never seen", "also missing"], timeout_ms=80)
    assert success is False
    assert set(remaining) == {"never seen", "also missing"}


def test_return_on_first_match(comms):
    comms.read_queue.put("only alpha")
    success, traces, remaining = comms.wait_for_trace(
        ["alpha", "beta"], timeout_ms=200, return_on_first_match=True)
    assert success is True
    assert remaining == ["beta"]


# ---------------------------------------------------------------- avoided

def test_avoided_response_fails_fast(comms):
    comms.read_queue.put("boom happened")
    success, traces, remaining = comms.wait_for_trace(
        ["never arrives"], avoided_responses=["boom"], timeout_ms=500)
    assert success is False


def test_required_match_survives_avoided_scan(comms):
    # regression: the avoided loop assigned its (None) search result over
    # the required match's metadata, so MATCHING collection dropped the
    # genuinely matched trace
    comms.read_queue.put("hello world")
    success, traces, remaining = comms.wait_for_trace(
        ["hello"],
        avoided_responses=["boom"],
        timeout_ms=200,
        trace_collect_pattern=DeviceTraceCollectPattern.MATCHING,
        trace_response_format=TraceResponseFormat.PROCESSED_RESPONSES,
    )
    assert success is True
    assert len(traces) == 1
    assert traces[0]["_regex_search_string"] == "hello"


# ---------------------------------------------------------------- formats

def test_processed_responses_expose_regex_groups(comms):
    comms.read_queue.put("count=42 done")
    success, traces, remaining = comms.wait_for_trace(
        [r"count=(?P<n>\d+)"],
        timeout_ms=200,
        trace_collect_pattern=DeviceTraceCollectPattern.MATCHING,
        trace_response_format=TraceResponseFormat.PROCESSED_RESPONSES,
    )
    assert success is True
    assert traces[0]["n"] == "42"


def test_raw_traces_returns_string(comms):
    comms.read_queue.put("plain line")
    success, traces, remaining = comms.wait_for_trace(
        ["plain"],
        timeout_ms=200,
        trace_response_format=TraceResponseFormat.RAW_TRACES,
    )
    assert success is True
    assert isinstance(traces, str)
    assert "plain line" in traces


def test_collect_all_keeps_unmatched_lines(comms):
    comms.read_queue.put("noise")
    comms.read_queue.put("signal")
    success, traces, remaining = comms.wait_for_trace(
        ["signal"],
        timeout_ms=300,
        trace_collect_pattern=DeviceTraceCollectPattern.ALL,
        trace_response_format=TraceResponseFormat.PROCESSED_RESPONSES,
    )
    assert success is True
    seen = [t["_trace"] for t in traces]
    assert seen == ["noise", "signal"]


def test_cmd_is_sent_before_waiting(comms):
    comms.read_queue.put("pong")
    success, traces, remaining = comms.wait_for_trace(
        ["pong"], cmd="ping", timeout_ms=200)
    assert success is True
    assert comms.write_queue.get_nowait() == "ping"


# ---------------------------------------------------------------- event maps

def test_wait_for_event_maps_events(comms):
    comms.set_event_map({
        Events.PING: r"pong=(?P<v>\d+)",
        Events.BOOT: r"booted",
    })
    comms.read_queue.put("pong=7")
    success, traces, remaining_events = comms.wait_for_event(
        [Events.PING], timeout_ms=200)
    assert success is True
    assert remaining_events == []
    assert traces[0]["_event"] == Events.PING
    assert traces[0]["v"] == "7"


def test_wait_for_event_reports_remaining_events(comms):
    comms.set_event_map({
        Events.PING: r"pong",
        Events.BOOT: r"booted",
    })
    comms.read_queue.put("pong")
    success, traces, remaining_events = comms.wait_for_event(
        [Events.PING, Events.BOOT], timeout_ms=80)
    assert success is False
    assert remaining_events == [Events.BOOT]


def test_event_map_duplicate_trace_raises_cleanly(comms):
    # regression: the handler caught an unimported name and NameError'd
    # exactly when a duplicate existed. match= pins the intended message,
    # which a NameError would not carry
    with pytest.raises(Exception, match="two of the same"):
        comms.set_event_map({
            Events.PING: "same regex",
            Events.CRASH: "same regex",
        })


def test_wait_for_event_requires_event_map(comms):
    assert comms.wait_for_event([Events.PING]) == (None, None, None)
