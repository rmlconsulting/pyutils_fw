import os
from abc import ABC, abstractmethod
import threading
import logging
from enum import IntEnum, auto

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)


class RelayGroupType(IntEnum):
    # only one can be active in the group
    EXCLUSIVE = auto()

    # all group members must be active. if you toggle one, toggle all
    FORCE_MATCHING = auto()

    # all group members must be active. reject requests to toggle a single relay
    CHECK_MATCHING = auto()

    # all group members must be updated together (mixed on/off allowed)
    SYNCED = auto()


class SeqGuard:
    """
    Persistent sequencing guard.
    - Holds a single shared BoundedSemaphore(1)
    - __enter__: acquire immediately
    - __exit__: release via Timer after delay_ms (or immediately if 0)
    """
    def __init__(self, delay_ms: int = 0):
        self._gate = threading.BoundedSemaphore(1)
        self._delay_ms = int(delay_ms) if delay_ms else 0

    def __enter__(self):
        self._gate.acquire()
        return self

    def __exit__(self, exc_type, exc, tb):
        if self._delay_ms > 0:
            t = threading.Timer(self._delay_ms / 1000.0, self._gate.release)
            t.daemon = True
            t.start()
        else:
            self._gate.release()


class RelayBase(ABC):
    """
    Abstract base class for a relay board with optional group behavior.
    Handles activation, deactivation, and toggling of relays while enforcing
    group constraints defined in `relay_groups`.
    """

    def __init__(self, num_relays, supports_autosense: bool = False, relay_groups: dict = {}, seq_delay_ms: int = 0):
        self._relay_groups = relay_groups
        self._relay_to_group = {}
        self._group_members = {}

        for relay_index, meta in self._relay_groups.get("relays", {}).items():
            group_name = meta.get("group_name")
            if group_name:
                self._relay_to_group[relay_index] = group_name
                self._group_members.setdefault(group_name, set()).add(relay_index)

        self.num_relays = num_relays
        self._lock = SeqGuard(seq_delay_ms)
        self._relay_status = {}

        self._flush_buffers()
        self.write_all_relays([])

        for i in range(num_relays):
            self._relay_status[i] = 0

    def _group_of(self, relay_index: int):
        return self._relay_to_group.get(relay_index)

    def _group_type(self, group_name: str):
        return self._relay_groups.get("groups", {}).get(group_name, {}).get("type")

    def _members(self, group_name: str) -> set[int]:
        return set(self._group_members.get(group_name, set()))

    def _current_on(self) -> set[int]:
        return {i for i, v in self._relay_status.items() if v}

    def _validate_parameters(self, relay_index: int | None, relay_list: list[int] | None) -> list[int]:
        if relay_index is not None and relay_list:
            raise ValueError("provide either relay_index or relay_list, not both")
        if relay_list is not None:
            if not relay_list:
                raise ValueError("relay_list is empty")
            targets = list(relay_list)
        else:
            if relay_index is None:
                raise ValueError("must provide relay_index or relay_list")
            targets = [relay_index]

        max_idx = max(targets)
        min_idx = min(targets)
        if max_idx >= self.num_relays or min_idx < 0:
            raise IndexError(f"relay indices out of range (0..{self.num_relays - 1})")

        return targets

    def _detect_group_conflicts(self, targets: list[int]) -> str | None:
        group_names = {self._group_of(t) for t in targets}
        if len(group_names) > 1:
            raise ValueError("all relays must belong to the same group or all be ungrouped")
        return next(iter(group_names))

    def _get_group_metadata(self, group_name: str | None):
        if group_name is None:
            return None, None, set()
        group_type = self._group_type(group_name)
        members = self._members(group_name)
        return group_name, group_type, members

    def _validate_group_consistency(self, targets: list[int]):
        group_name = self._detect_group_conflicts(targets)
        return self._get_group_metadata(group_name)

    def _apply_delta(self, desired_on: set[int]) -> None:
        desired_on = {i for i in desired_on if 0 <= i < self.num_relays}
        current_on = self._current_on()

        adds = desired_on - current_on
        removes = current_on - desired_on
        changes = len(adds) + len(removes)

        if changes == 0:
            return

        if changes == 1:
            idx = next(iter(adds or removes))
            with self._lock:
                if idx in adds:
                    self._activate_relay(idx)
                else:
                    self._deactivate_relay(idx)
            return

        self._write_all_relays_raw(sorted(desired_on))

    def _apply_plan(self, desired_on: set[int]) -> None:
        self._apply_delta(desired_on)

    @abstractmethod
    def _activate_relay(self, relay_index: int) -> None:
        pass

    @abstractmethod
    def _deactivate_relay(self, relay_index: int) -> None:
        pass

    def activate_relay(self, relay_index: int = None, relay_list: list[int] = None) -> None:
        targets = self._validate_parameters(relay_index, relay_list)
        group_name, group_type, members = self._validate_group_consistency(targets)
        current_on = self._current_on()
        desired_on = set(current_on)

        if group_name is None:
            desired_on |= set(targets)
            self._apply_plan(desired_on)
            return

        if group_type == RelayGroupType.EXCLUSIVE:
            if len(targets) != 1:
                raise ValueError(f"exclusive group '{group_name}' allows activating exactly one member")
            chosen = targets[0]
            desired_on -= members
            desired_on.add(chosen)

        elif group_type == RelayGroupType.FORCE_MATCHING:
            desired_on |= members

        elif group_type == RelayGroupType.CHECK_MATCHING:
            if set(targets) != members:
                raise ValueError(f"check_matching group '{group_name}' requires all members: {sorted(members)}")
            desired_on |= members

        elif group_type == RelayGroupType.SYNCED:
            if set(targets) != members:
                raise ValueError(f"synced group '{group_name}' requires all members be updated together")
            desired_on |= set(targets)

        self._apply_plan(desired_on)

    def deactivate_relay(self, relay_index: int = None, relay_list: list[int] = None) -> None:
        targets = self._validate_parameters(relay_index, relay_list)
        group_name, group_type, members = self._validate_group_consistency(targets)
        current_on = self._current_on()
        desired_on = set(current_on)

        if group_name is None:
            desired_on -= set(targets)
            self._apply_plan(desired_on)
            return

        if group_type == RelayGroupType.EXCLUSIVE:
            desired_on -= set(targets)

        elif group_type == RelayGroupType.FORCE_MATCHING:
            desired_on -= members

        elif group_type == RelayGroupType.CHECK_MATCHING:
            if set(targets) != members:
                raise ValueError(f"check_matching group '{group_name}' requires all members: {sorted(members)}")
            desired_on -= members

        elif group_type == RelayGroupType.SYNCED:
            if set(targets) != members:
                raise ValueError(f"synced group '{group_name}' requires all members be updated together")
            desired_on -= set(targets)

        self._apply_plan(desired_on)

    def toggle_relay(self, relay_index: int) -> None:
        if not (0 <= relay_index < self.num_relays):
            raise IndexError(f"relay_index {relay_index} out of range (0..{self.num_relays - 1})")

        group_name = self._group_of(relay_index)
        current_on = self._current_on()
        desired_on = set(current_on)

        if group_name is None:
            if relay_index in current_on:
                desired_on.discard(relay_index)
            else:
                desired_on.add(relay_index)
            self._apply_plan(desired_on)
            return

        group_type = self._group_type(group_name)
        members = self._members(group_name)

        if group_type == RelayGroupType.EXCLUSIVE:
            if relay_index in current_on:
                desired_on.discard(relay_index)
            else:
                desired_on -= members
                desired_on.add(relay_index)

        elif group_type == RelayGroupType.FORCE_MATCHING:
            any_on = any(m in current_on for m in members)
            if any_on:
                desired_on -= members
            else:
                desired_on |= members

        elif group_type == RelayGroupType.CHECK_MATCHING:
            raise ValueError(f"check_matching group '{group_name}' forbids single-member toggle")

        elif group_type == RelayGroupType.SYNCED:
            raise ValueError(f"synced group '{group_name}' must be toggled as a full group via relay_list")

        self._apply_plan(desired_on)

    def _flush_buffers(self) -> None:
        pass

    def autosense_hardware(self) -> None:
        pass

    def _write_all_relays_raw(self, on_channels: list[int]) -> None:
        on_set = set(on_channels)
        with self._lock:
            for channel in range(self.num_relays):
                if channel in on_set:
                    self._activate_relay(channel)
                else:
                    self._deactivate_relay(channel)

    def write_all_relays(self, on_channels: list[int]) -> None:
        if on_channels:
            if min(on_channels) < 0 or max(on_channels) >= self.num_relays:
                raise IndexError(f"relay indices out of range (0..{self.num_relays - 1})")

        desired_on = set(on_channels)
        current_on = self._current_on()
        fixed_on = set(desired_on)

        for group_name, members in self._group_members.items():
            group_type = self._group_type(group_name)
            if not group_type:
                continue

            cur_on = current_on & members
            des_on = fixed_on & members
            adds = des_on - cur_on
            removes = cur_on - des_on
            size = len(members)

            if group_type == RelayGroupType.EXCLUSIVE:
                if len(des_on) > 1:
                    raise ValueError(f"exclusive group '{group_name}' allows at most one ON, requested {sorted(des_on)}")
                if len(adds) == 1:
                    only = next(iter(adds))
                    fixed_on -= members
                    fixed_on.add(only)
                elif len(des_on) == 1 and len(adds) == 0:
                    only = next(iter(des_on))
                    fixed_on -= (members - {only})

            elif group_type == RelayGroupType.FORCE_MATCHING:
                if adds and not removes:
                    fixed_on |= members
                elif removes and not adds:
                    fixed_on -= members
                elif adds and removes:
                    raise ValueError(f"force_matching group '{group_name}' has mixed intent")
                else:
                    count = len(des_on)
                    if 0 < count < size:
                        raise ValueError(f"force_matching group '{group_name}' cannot be partial")

            elif group_type == RelayGroupType.CHECK_MATCHING:
                count = len(des_on)
                if 0 < count < size:
                    raise ValueError(f"check_matching group '{group_name}' must be all-on or all-off")
                if adds and not removes:
                    fixed_on |= members
                elif removes and not adds:
                    fixed_on -= members
                elif adds and removes:
                    raise ValueError(f"check_matching group '{group_name}' has mixed intent")

            elif group_type == RelayGroupType.SYNCED:
                # write all by definition changes all of the relays in the group.
                # it is not possible to determine further intent here
                pass

        self._write_all_relays_raw(sorted(fixed_on))

    def read_all_relays(self) -> list[int]:
        return [index for index, active in self._relay_status.items() if active]

    def is_relay_active(self, relay_index: int) -> bool:
        if relay_index >= self.num_relays:
            raise Exception(f"relay board only has {self.num_relays} relays")
        return self._relay_status[relay_index] == 1

