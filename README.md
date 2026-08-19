# pyutils_fw

Firmware-centric Python utilities: relay board control, device
communication (serial / SEGGER J-Link RTT), and process helpers for
automated test and development workflows against embedded hardware.

> **0.1.0 is the first packaged release.** Earlier revisions were a
> collection of `sys.path`-hacked directories; everything now lives under
> one installable `pyutils_fw` package. autoHILT pins this package at an
> exact version (`pyutils-fw==0.1.0`).

## Install

```bash
pip install pyutils-fw            # once published to PyPI
pip install pyutils-fw[process]   # + psutil, for run_process child cleanup

# from source
git clone https://github.com/rmlconsulting/pyutils_fw.git
cd pyutils_fw
pip install -e ".[process]"
```

Requires Python 3.9+. Hard dependencies: `pyserial`, `bidict`.

## What's in the box

| Subpackage                 | What it does                                                                  |
| -------------------------- | ----------------------------------------------------------------------------- |
| `pyutils_fw.relays`         | Relay board control: state cache, relay grouping policy, Numato USB modules  |
| `pyutils_fw.device_comms`   | Talk to devices over serial or J-Link RTT: trace matching, command/response  |
| `pyutils_fw.run_process`    | Run a CLI process and react to its stdout in real time                       |
| `pyutils_fw.tee`            | Mirror stdout/stderr into timestamped log files                              |
| `pyutils_fw.event_generator`| Fire events on fixed/random schedules                                        |
| `pyutils_fw.encrypt`        | AES file encryption (needs `pyAesCrypt`, not a declared dep)                 |

Per-module docs: [relays](pyutils_fw/relays/README.md) ·
[device_comms](pyutils_fw/device_comms/README.md) ·
[run_process](pyutils_fw/run_process/README.md). Known-but-unfixed defects
are recorded in [KNOWN-ISSUES.md](KNOWN-ISSUES.md).

## Quick start: relays

```python
from pyutils_fw.relays import NumatoDevice

# POSIX device path or Windows COM name ("COM3") both work
with NumatoDevice(path="/dev/tty.usbmodem1101", num_relays=4) as board:
    board.activate_relay(relay_index=0)
    board.activate_relay(relay_index=2, auto_off_ms=500)   # timed pulse

    active = board.read_all_relays()          # from the state cache
    active = board.read_all_relays(force=True) # re-read from hardware

    board.write_all_relays([1, 3])            # exactly these on, rest off
    board.deactivate_all()                    # everything back to rest
# serial port closed on exit
```

Relays can be grouped (`EXCLUSIVE`, `FORCE_MATCHING`, `CHECK_MATCHING`,
`SYNCED`) and the base class enforces the policy on every call - see
[the relays README](pyutils_fw/relays/README.md).

## Quick start: device comms

```python
from pyutils_fw.device_comms import SerialCommsDevice, SerialCommsDeviceConfig

config = SerialCommsDeviceConfig(serial_device_path="/dev/tty.usbmodem123",
                                 baud_rate=115200)
device = SerialCommsDevice(config)
device.start_capturing_traces()

success, traces, remaining = device.wait_for_trace(
    cmd="version",
    required_responses=r"fw v(?P<ver>\d+\.\d+\.\d+)",
    timeout_ms=2000,
)
```

`JLinkDevice` shares the same base class and API over SEGGER RTT
(POSIX-only for now - see KNOWN-ISSUES.md).

## Development

```bash
pip install -e ".[process]" pytest
pytest -q            # hardware-free suite, runs in about a second
python -m build      # sdist + wheel
```

CI runs the suite on Linux, macOS and Windows against Python 3.9 and 3.12,
builds the distributions, and verifies the wheel contents.

## Support

Bugs: report reproduction steps and OS to bugs@rmlconsulting.dev - or just
open a PR. Questions and customization requests:
questions@rmlconsulting.dev.

## License

BSD 2-Clause. See [LICENSE](LICENSE).
