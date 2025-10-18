# named_relays.py
from dataclasses import dataclass
from typing import Any, Dict, List
from relay_base import RelayGroupType


# ======================================================================
# Single Relay Wrapper
# ======================================================================

@dataclass(frozen=True)
class NamedRelay:
    """
    Simple wrapper for operating a single relay by name.
    Keeps calls single-shot so RelayBase enforces any policy.
    """
    board_name: str
    board: Any
    index: int
    name: str

    # ------------------------------------------------------------------
    # Basic control
    # ------------------------------------------------------------------

    def activate(self) -> None:
        """Turn this relay ON."""
        self.board.activate_relay(relay_index=self.index)

    def deactivate(self) -> None:
        """Turn this relay OFF."""
        self.board.deactivate_relay(relay_index=self.index)

    def toggle(self) -> None:
        """Toggle this relay state."""
        self.board.toggle_relay(self.index)

    def is_active(self) -> bool:
        """Return True if relay is currently active."""
        return self.board.is_relay_active(self.index)

    def __repr__(self) -> str:
        return f"<NamedRelay {self.name} -> {self.board_name}[{self.index}]>"


# ======================================================================
# Group Wrapper
# ======================================================================

@dataclass(frozen=True)
class NamedRelayGroup:
    """
    Simple wrapper for operating on a relay group by names, deferring all
    policy enforcement to RelayBase.
    """
    board_name: str
    board: Any
    name: str
    members: List[int]                 # original board indices for this group
    gtype: RelayGroupType
    name_to_index: Dict[str, int]      # relay name -> original index

    # ------------------------------------------------------------------
    # Single-target helper (exclusive intent)
    # ------------------------------------------------------------------

    def activate_exclusive(self, relay_name: str) -> None:
        """
        Turn ON exactly this member and turn OFF the rest of this group,
        atomically. Non-group relays are preserved as-is.
        Works for any group type; RelayBase will enforce legality.
        """
        target_idx = self._to_index(relay_name)
        group_set = set(self.members)
        current_on = self._current_on_indices()
        desired_on = (current_on - group_set) | {target_idx}
        self.board.write_all_relays(sorted(desired_on))

    def deactivate_exclusive(self, relay_name: str) -> None:
        """Turn OFF exactly this member (others in the group left as-is)."""
        idx = self._to_index(relay_name)
        self.board.deactivate_relay(relay_index=idx)

    # ------------------------------------------------------------------
    # Group-wide helpers
    # ------------------------------------------------------------------

    def activate_all(self) -> None:
        """Activate all members of this group (base enforces policy)."""
        self.board.activate_relay(relay_list=self.members)

    def deactivate_all(self) -> None:
        """Deactivate all members of this group (base enforces policy)."""
        self.board.deactivate_relay(relay_list=self.members)

    # ------------------------------------------------------------------
    # Partial updates (members only)
    # ------------------------------------------------------------------

    def activate(self, relay_names: List[str]) -> None:
        """
        Activate the provided relays as a single operation.
        Others (in group or outside) are left untouched.
        Base class will enforce legality of partial updates.
        """
        indices = self._to_indices(relay_names)
        self.board.activate_relay(relay_list=indices)

    def deactivate(self, relay_names: List[str]) -> None:
        """
        Deactivate the provided relays as a single operation.
        Others (in group or outside) are left untouched.
        Base class will enforce legality of partial updates.
        """
        indices = self._to_indices(relay_names)
        self.board.deactivate_relay(relay_list=indices)

    def update_group(self, active_relay_names: List[str]) -> None:
        """
        Provided relays are ACTIVE; all other members in this group are explicitly
        deactivated. Non-group relays are preserved as-is.

        Ideal for SYNCED groups: applies the entire group pattern atomically.
        """
        active_idx = set(self._to_indices(active_relay_names))
        group = set(self.members)
        current_on = self._current_on_indices()
        desired_on = (current_on - group) | active_idx
        self.board.write_all_relays(sorted(desired_on))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _current_on_indices(self) -> set[int]:
        """
        Normalize board.read_all_relays() to a set of ON indices.
        Accepts either a 0/1 vector (len == num_relays) or a list of indices.
        """
        raw = self.board.read_all_relays()
        if isinstance(raw, list) and len(raw) == getattr(self.board, "num_relays", len(raw)) \
           and all(x in (0, 1, 0.0, 1.0) for x in raw):
            return {i for i, v in enumerate(raw) if int(v) == 1}
        return set(int(i) for i in raw)

    def _to_index(self, relay_name: str) -> int:
        try:
            idx = self.name_to_index[relay_name]
        except KeyError:
            valid = ", ".join(sorted(self.name_to_index.keys()))
            raise KeyError(f"'{relay_name}' not found in group '{self.name}'. Valid: {valid}")
        if idx not in self.members:
            raise ValueError(
                f"Index {idx} for '{relay_name}' not in group '{self.name}' members {self.members}"
            )
        return idx

    def _to_indices(self, relay_names: List[str]) -> List[int]:
        return sorted({self._to_index(n) for n in relay_names})

    def __repr__(self) -> str:
        return (
            f"<NamedRelayGroup {self.name} ({self.gtype.name}) "
            f"on {self.board_name} members={self.members}>"
        )

