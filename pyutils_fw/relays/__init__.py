"""Relay board control.

Public interface:
    RelayBase        - abstract base class: state cache, group policy,
                       sequencing guard, lifecycle (close/deactivate_all)
    RelayGroupType   - EXCLUSIVE / FORCE_MATCHING / CHECK_MATCHING / SYNCED
    NumatoDevice     - Numato USB relay/GPIO/ADC modules
    NamedRelay       - operate a single relay by name
    NamedRelayGroup  - operate a relay group by member names
    NumatoNode       - channel node selector (relay / gpio / adc) for the
                       Numato-specific GPIO and ADC calls

``lcus_relay_board`` is present but deprecated/non-functional - see
KNOWN-ISSUES.md at the repository root.
"""

from .relay_base import RelayBase, RelayGroupType, SeqGuard
from .numato_relay_board import NumatoDevice, NumatoNode
from .named_relay_utils import NamedRelay, NamedRelayGroup

__all__ = [
    "RelayBase",
    "RelayGroupType",
    "SeqGuard",
    "NumatoDevice",
    "NumatoNode",
    "NamedRelay",
    "NamedRelayGroup",
]
