"""The import surface autoHILT (and the README) depend on, plus package data."""

import os
import sys

import pytest


def test_version():
    import pyutils_fw
    assert pyutils_fw.__version__ == "0.1.0"


def test_relays_public_surface():
    from pyutils_fw.relays import (   # noqa: F401
        NamedRelay,
        NamedRelayGroup,
        NumatoDevice,
        RelayBase,
        RelayGroupType,
    )


def test_device_comms_public_surface():
    from pyutils_fw.device_comms import (   # noqa: F401
        DeviceCommsBase,
        DeviceTraceCollectPattern,
        JLinkDevice,
        JLinkTransportConfig,
        SerialCommsDevice,
        SerialCommsDeviceConfig,
        StartupStatus,
        TraceEvent,
        TraceResponseFormat,
    )


def test_seed_recorded_class_paths_resolve():
    # autoHILT's seed data records these exact dotted paths
    import pyutils_fw.relays
    import pyutils_fw.device_comms

    assert pyutils_fw.relays.NumatoDevice is not None
    assert pyutils_fw.device_comms.SerialCommsDevice is not None
    assert pyutils_fw.device_comms.JLinkDevice is not None


def test_other_subpackages_import():
    from pyutils_fw.run_process import RunProcess   # noqa: F401
    from pyutils_fw.tee import Tee                  # noqa: F401
    from pyutils_fw.event_generator import (        # noqa: F401
        EventCoordinator,
        EventGeneratorBase,
        EventTiming,
        FunctionCaller,
        IntervalType,
    )
    import pyutils_fw.encrypt                       # noqa: F401


def test_power_on_jlink_ships_with_the_package():
    from pyutils_fw.device_comms import jlink_device
    script = os.path.join(os.path.dirname(jlink_device.__file__), "power_on.jlink")
    assert os.path.exists(script)


def test_run_process_without_psutil_names_the_extra(monkeypatch):
    from pyutils_fw.run_process import RunProcess

    process = RunProcess("echo hi")

    # hide psutil from the lazy import
    monkeypatch.setitem(sys.modules, "psutil", None)

    with pytest.raises(RuntimeError, match=r"pyutils-fw\[process\]"):
        process._RunProcess__kill_child_processes(999999)
