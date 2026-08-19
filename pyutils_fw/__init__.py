"""pyutils_fw - firmware-centric Python utilities.

Subpackages:
    relays          - relay board control (Numato USB relay/GPIO/ADC modules)
    device_comms    - device communication (serial, SEGGER J-Link RTT)
    run_process     - run a CLI process and react to its output
    tee             - mirror stdout/stderr to timestamped log files
    event_generator - timed/random event generation helpers
    encrypt         - AES file encryption helpers (undeclared extra dep,
                      see KNOWN-ISSUES.md)

Subpackages are imported explicitly (``from pyutils_fw.relays import
NumatoDevice``) so that importing :mod:`pyutils_fw` itself stays cheap and
never drags in optional dependencies.
"""

__version__ = "0.1.0"
