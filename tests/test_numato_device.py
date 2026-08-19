"""NumatoDevice protocol framing against a scripted fake serial port.

The fake speaks the Numato wire protocol the driver expects: every
command is echoed back terminated by CR, then the response (possibly
empty) arrives followed by the ``>`` prompt. It keeps real channel
state, decodes the 0-9/a-v channel addressing, and records every
command so tests can assert the exact frames sent.
"""

import serial

import pytest

from pyutils_fw.relays import NumatoDevice, NumatoNode


def mask_width_chars(max_channels):
    if max_channels >= 64:
        return 16
    if max_channels >= 32:
        return 8
    if max_channels >= 16:
        return 4
    return 2


class FakeNumatoSerial:
    def __init__(self, num_relays=4, num_gpio=0, num_adc=0,
                 fw="1.0.0", board_id="FAKE0001", adc_values=None):
        self.num_relays = num_relays
        self.num_gpio = num_gpio
        self.num_adc = num_adc
        self.fw = fw
        self.board_id = board_id
        self.adc_values = adc_values or {}
        self.relay_state = {}
        self.gpio_state = {}
        self.commands = []
        self.is_open = True
        self._rx = b""

    # -- pyserial surface the driver touches --------------------------------

    def write(self, data):
        cmd = data.decode("ascii").rstrip("\r")
        self.commands.append(cmd)
        resp = self._respond(cmd)
        payload = cmd + "\r" + "\n" + (resp or "") + "\r\n>"
        self._rx += payload.encode("ascii")

    def read_until(self, expected=b"\n", size=None):
        idx = self._rx.find(expected)
        if idx == -1:
            data, self._rx = self._rx, b""
            return data
        end = idx + len(expected)
        data, self._rx = self._rx[:end], self._rx[end:]
        return data

    def flushInput(self):
        self._rx = b""

    def flushOutput(self):
        pass

    def close(self):
        self.is_open = False

    # -- protocol ------------------------------------------------------------

    @staticmethod
    def _chan(token):
        """Inverse of the driver's number-to-alpha mapping (a=10 .. v=31)."""
        if token.isdigit():
            return int(token)
        return ord(token) - 87

    def _mask(self, state, max_channels):
        value = 0
        for channel, on in state.items():
            if on:
                value |= 1 << channel
        return "{0:0{1}x}".format(value, mask_width_chars(max_channels))

    def _respond(self, cmd):
        if cmd == "":
            return ""
        if cmd == "ver":
            return self.fw
        if cmd == "id get":
            return self.board_id

        parts = cmd.split()

        if parts[0] == "relay":
            if parts[1] == "on":
                self.relay_state[self._chan(parts[2])] = 1
                return ""
            if parts[1] == "off":
                self.relay_state[self._chan(parts[2])] = 0
                return ""
            if parts[1] == "read":
                channel = self._chan(parts[2])
                if channel >= self.num_relays:
                    return ""          # real boards go silent past the end
                return "on" if self.relay_state.get(channel) else "off"
            if parts[1] == "readall":
                return self._mask(self.relay_state, self.num_relays)
            if parts[1] == "writeall":
                value = int(parts[2], 16)
                for channel in range(self.num_relays):
                    self.relay_state[channel] = (value >> channel) & 1
                return ""
            if parts[1] == "iomask":
                return ""

        if parts[0] == "gpio":
            if parts[1] == "read":
                channel = self._chan(parts[2])
                if channel >= self.num_gpio:
                    return ""
                return str(self.gpio_state.get(channel, 0))
            if parts[1] == "readall":
                if self.num_gpio == 0:
                    return ""
                return self._mask(self.gpio_state, self.num_gpio)
            if parts[1] in ("set", "clear"):
                self.gpio_state[self._chan(parts[2])] = 1 if parts[1] == "set" else 0
                return ""
            if parts[1] == "iodir":
                return ""

        if parts[0] == "adc" and parts[1] == "read":
            channel = self._chan(parts[2])
            if channel >= self.num_adc:
                return ""
            return str(self.adc_values.get(channel, 512))

        return ""


@pytest.fixture
def numato(monkeypatch, tmp_path):
    """Factory: build a NumatoDevice wired to a FakeNumatoSerial."""

    def make(fake=None, **device_kwargs):
        fake = fake or FakeNumatoSerial(num_relays=device_kwargs.get("num_relays", 4),
                                        num_gpio=device_kwargs.get("num_gpio", 4),
                                        num_adc=device_kwargs.get("num_adc", 4))
        monkeypatch.setattr(serial, "Serial", lambda *args, **kwargs: fake)
        device_path = tmp_path / "ttyFAKE"
        device_path.touch()
        device_kwargs.setdefault("num_relays", 4)
        device_kwargs.setdefault("num_gpio", 4)
        device_kwargs.setdefault("num_adc", 4)
        device = NumatoDevice(str(device_path), **device_kwargs)
        return device, fake

    return make


# ---------------------------------------------------------------- construction

def test_constructor_reads_fw_version_and_id(numato):
    device, fake = numato()
    assert device.fw_version == "1.0.0"
    assert device.id == "FAKE0001"
    assert device.get_fw_version() == "1.0.0"
    assert device.get_id() == "FAKE0001"


def test_construction_resets_relays(numato):
    device, fake = numato()
    assert "relay off 0" in fake.commands
    assert "relay off 3" in fake.commands
    assert device.read_all_relays() == []


def test_autodiscovery_defaults(numato):
    # regression x2: the documented default constructor call crashed on
    # relay_groups=None, and discovery crashed at channel 10 because
    # is_set() mapped to alpha and read() mapped again
    fake = FakeNumatoSerial(num_relays=16, num_gpio=4, num_adc=2)
    device, fake = numato(fake=fake, num_relays=0, num_gpio=0, num_adc=0)

    assert device.num_relays == 16
    assert device.num_gpio == 4
    assert device.num_adc == 2
    # discovery had to address channels past 9 in alpha form
    assert "relay read a" in fake.commands


def test_windows_com_port_accepted(monkeypatch):
    # regression: __init__ ran abspath + os.path.exists on the path, which
    # mangled and then rejected Windows COM port names before pyserial ever
    # saw them
    import sys as _sys

    fake = FakeNumatoSerial(num_relays=4, num_gpio=4, num_adc=4)
    monkeypatch.setattr(serial, "Serial", lambda *args, **kwargs: fake)
    monkeypatch.setattr(_sys, "platform", "win32")

    device = NumatoDevice("com3", num_relays=4, num_gpio=4, num_adc=4)
    assert device.path == "COM3"
    assert device.fw_version == "1.0.0"


# ---------------------------------------------------------------- addressing

def test_channels_past_nine_use_alpha_addressing(numato):
    device, fake = numato(num_relays=32, num_gpio=1, num_adc=1,
                          fake=FakeNumatoSerial(num_relays=32, num_gpio=1, num_adc=1))
    device.activate_relay(relay_index=10)
    assert "relay on a" in fake.commands
    device.activate_relay(relay_index=31)
    assert "relay on v" in fake.commands

    device.deactivate_relay(relay_index=10)
    assert "relay off a" in fake.commands


def test_is_set_roundtrip_past_nine(numato):
    # regression: is_set() double-mapped the channel and raised for >= 10
    device, fake = numato(num_relays=32, num_gpio=1, num_adc=1,
                          fake=FakeNumatoSerial(num_relays=32, num_gpio=1, num_adc=1))
    device.activate_relay(relay_index=10)
    assert device.is_set(NumatoNode.relay, 10) is True
    device.deactivate_relay(relay_index=10)
    assert device.is_set(NumatoNode.relay, 10) is False


def test_is_set_roundtrip_single_digit(numato):
    device, fake = numato()
    device.set(NumatoNode.relay, 3)
    assert device.is_set(NumatoNode.relay, 3) is True
    device.clear(NumatoNode.relay, 3)
    assert device.is_set(NumatoNode.relay, 3) is False


# ---------------------------------------------------------------- masks

def test_writeall_mask_width_32_channels(numato):
    device, fake = numato(num_relays=32, num_gpio=1, num_adc=1,
                          fake=FakeNumatoSerial(num_relays=32, num_gpio=1, num_adc=1))
    device.writeall(NumatoNode.relay, [0, 1, 10])
    assert "relay writeall 00000403" in fake.commands
    assert device.readall(NumatoNode.relay) == [0, 1, 10]


def test_writeall_mask_width_4_channels(numato):
    device, fake = numato()
    device.writeall(NumatoNode.relay, [0, 2])
    assert "relay writeall 05" in fake.commands
    assert device.readall(NumatoNode.relay) == [0, 2]


def test_writeall_does_not_mutate_caller_list(numato):
    device, fake = numato()
    channels = [2, 0]
    device.writeall(NumatoNode.relay, channels)
    assert channels == [2, 0]


def test_writeall_rejects_out_of_range(numato):
    device, fake = numato()
    with pytest.raises(Exception):
        device.writeall(NumatoNode.relay, [9])


# ---------------------------------------------------------------- cache contract

def test_read_all_relays_uses_cache(numato):
    device, fake = numato()
    device.activate_relay(relay_index=1)
    read_commands_before = [c for c in fake.commands if c.startswith("relay read")]

    assert device.read_all_relays() == [1]

    read_commands_after = [c for c in fake.commands if c.startswith("relay read")]
    assert read_commands_before == read_commands_after, \
        "read_all_relays() without force must not touch hardware"


def test_read_all_relays_force_reads_hardware(numato):
    device, fake = numato()
    device.activate_relay(relay_index=1)

    # hardware changes behind the driver's back
    fake.relay_state[3] = 1

    assert device.read_all_relays() == [1]
    assert device.read_all_relays(force=True) == [1, 3]
    assert device.read_all_relays() == [1, 3]


# ---------------------------------------------------------------- repaired calls

def test_setmask_executes(numato):
    # regression: referenced undefined 'max_channel'
    device, fake = numato(num_relays=32, num_gpio=1, num_adc=1,
                          fake=FakeNumatoSerial(num_relays=32, num_gpio=1, num_adc=1))
    device.setmask(NumatoNode.relay, "00")
    assert "relay iomask 00" in fake.commands


def test_setmask_rejects_oversized_mask(numato):
    device, fake = numato()   # 4 relays; "00" spans 8 channels
    with pytest.raises(Exception):
        device.setmask(NumatoNode.relay, "00")


def test_set_iodir_executes(numato):
    # regression: three self.device.* references and a wrong method name
    device, fake = numato(num_gpio=8,
                          fake=FakeNumatoSerial(num_relays=4, num_gpio=8, num_adc=4))
    device.set_iodir(NumatoNode.gpio, [0, 1])
    assert "gpio iodir 03" in fake.commands


# ---------------------------------------------------------------- lifecycle

def test_close_closes_serial(numato):
    device, fake = numato()
    device.close()
    assert fake.is_open is False
    device.close()   # idempotent


def test_context_manager(numato):
    device, fake = numato()
    with device as d:
        d.activate_relay(relay_index=0)
    assert fake.is_open is False


def test_deactivate_all(numato):
    device, fake = numato()
    device.activate_relay(relay_list=[0, 2])
    device.deactivate_all()
    assert device.read_all_relays() == []
    assert fake.relay_state.get(0) == 0
    assert fake.relay_state.get(2) == 0
