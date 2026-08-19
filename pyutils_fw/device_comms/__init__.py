"""Device communication (serial, SEGGER J-Link RTT).

Public interface:
    DeviceCommsBase           - abstract base: queues, hardware mutex,
                                trace matching (wait_for_trace/wait_for_event)
    StartupStatus             - UNKNOWN / SUCCESS / ERROR
    TraceResponseFormat       - RAW_TRACES / PROCESSED_RESPONSES
    DeviceTraceCollectPattern - LAST_ONLY / MATCHING / ALL
    TraceEvent                - one matched trace with its regex groups
    SerialCommsDevice         - serial transport
    SerialCommsDeviceConfig   - its config dataclass
    JLinkDevice               - J-Link RTT transport (POSIX-only today,
                                see KNOWN-ISSUES.md)
    JLinkTransportConfig      - its config dataclass
    JLinkTransportInterface   - debug interface selector (SWD)
"""

from .device_comms_base import (
    DeviceCommsBase,
    StartupStatus,
    TraceResponseFormat,
    DeviceTraceCollectPattern,
    TraceEvent,
    SubprocessStartError,
    SubprocessShutdownError,
)
from .serial_device import SerialCommsDevice, SerialCommsDeviceConfig
from .jlink_device import JLinkDevice, JLinkTransportConfig, JLinkTransportInterface

__all__ = [
    "DeviceCommsBase",
    "StartupStatus",
    "TraceResponseFormat",
    "DeviceTraceCollectPattern",
    "TraceEvent",
    "SubprocessStartError",
    "SubprocessShutdownError",
    "SerialCommsDevice",
    "SerialCommsDeviceConfig",
    "JLinkDevice",
    "JLinkTransportConfig",
    "JLinkTransportInterface",
]
