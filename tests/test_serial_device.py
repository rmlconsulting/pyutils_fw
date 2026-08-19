"""does_device_exist normalization and SerialCommsDeviceConfig."""

import os
import sys

import pytest

from pyutils_fw.device_comms import SerialCommsDevice, SerialCommsDeviceConfig


def make_device(path="/dev/does-not-matter"):
    return SerialCommsDevice(SerialCommsDeviceConfig(
        serial_device_path=path, baud_rate=115200))


# ---------------------------------------------------------------- posix-style

def test_existing_path_returns_absolute_path(tmp_path):
    device_node = tmp_path / "ttyFAKE"
    device_node.touch()
    result = make_device().does_device_exist(str(device_node))
    assert result == str(device_node)
    assert isinstance(result, str)


def test_missing_path_returns_none(tmp_path):
    result = make_device().does_device_exist(str(tmp_path / "nope"))
    assert result is None


def test_env_vars_are_expanded(tmp_path, monkeypatch):
    device_node = tmp_path / "ttyENV"
    device_node.touch()
    monkeypatch.setenv("PYUTILS_FW_TEST_DEV", str(device_node))
    result = make_device().does_device_exist("$PYUTILS_FW_TEST_DEV")
    assert result == str(device_node)


# ---------------------------------------------------------------- windows COM

class _FakePort:
    def __init__(self, device):
        self.device = device


def test_com_port_returns_name_not_bool(monkeypatch):
    # regression: the Windows branch returned a bool, which callers fed
    # straight into serial.Serial(); it was also unreachable because
    # abspath() had already turned "COM3" into "<cwd>/COM3"
    import serial.tools.list_ports

    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(serial.tools.list_ports, "comports",
                        lambda: [_FakePort("COM3"), _FakePort("COM7")])

    result = make_device().does_device_exist("com3")
    assert result == "COM3"
    assert isinstance(result, str)


def test_com_port_missing_returns_none(monkeypatch):
    import serial.tools.list_ports

    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(serial.tools.list_ports, "comports",
                        lambda: [_FakePort("COM3")])

    assert make_device().does_device_exist("COM9") is None


# ---------------------------------------------------------------- config

def test_config_encoding_defaults_to_latin1():
    config = SerialCommsDeviceConfig(serial_device_path="/dev/x", baud_rate=9600)
    assert config.encoding == "latin-1"
    assert config.name == "SerialCommsDevice"
    assert config.device_recovery_time == 0


def test_config_encoding_is_configurable():
    config = SerialCommsDeviceConfig(
        serial_device_path="/dev/x", baud_rate=9600, encoding="utf-8")
    assert config.encoding == "utf-8"


def test_config_type_is_enforced():
    with pytest.raises(AssertionError):
        SerialCommsDevice({"serial_device_path": "/dev/x"})
