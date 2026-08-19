"""RelayBase state/group logic, no hardware.

FakeBoard records every hardware write and keeps a separate "physical"
state so the cache-vs-hardware semantics of read_all_relays(force=...)
are observable.
"""

import time

import pytest

from pyutils_fw.relays import (
    NamedRelay,
    NamedRelayGroup,
    RelayBase,
    RelayGroupType,
)


class FakeBoard(RelayBase):
    def __init__(self, num_relays=4, relay_groups=None, seq_delay_ms=0):
        self.hw_writes = []
        self.hw_state = {}
        self.read_relay_calls = 0
        super().__init__(
            num_relays,
            supports_autosense=False,
            relay_groups=relay_groups,
            seq_delay_ms=seq_delay_ms,
        )

    def _activate_relay(self, relay_index):
        self.hw_writes.append(("on", relay_index))
        self.hw_state[relay_index] = 1
        self._relay_status[relay_index] = 1

    def _deactivate_relay(self, relay_index):
        self.hw_writes.append(("off", relay_index))
        self.hw_state[relay_index] = 0
        self._relay_status[relay_index] = 0

    def read_relay(self, relay_index):
        self.read_relay_calls += 1
        return self.hw_state.get(relay_index, 0)


def make_board(**kwargs):
    board = FakeBoard(**kwargs)
    # construction resets every channel; start each test with a clean log
    board.hw_writes.clear()
    return board


def group_config(group_types, assignments):
    """group_types: {name: RelayGroupType}; assignments: {index: name}"""
    return {
        "groups": {n: {"type": t} for n, t in group_types.items()},
        "relays": {i: {"group_name": g} for i, g in assignments.items()},
    }


# ---------------------------------------------------------------- construction

def test_constructs_with_relay_groups_none():
    # regression: RelayBase.__init__ read relay_groups.get(...) and
    # AttributeError'd on the None default subclasses pass
    board = FakeBoard(relay_groups=None)
    assert board.read_all_relays() == []


def test_construction_resets_all_relays():
    board = FakeBoard(num_relays=3)
    assert ("off", 0) in board.hw_writes
    assert ("off", 1) in board.hw_writes
    assert ("off", 2) in board.hw_writes


def test_group_state_not_shared_between_instances():
    a = make_board()
    b = make_board()
    assert a._relay_groups is not b._relay_groups


# ---------------------------------------------------------------- basic ops

def test_activate_deactivate_single():
    board = make_board()
    board.activate_relay(relay_index=1)
    assert board.is_relay_active(1)
    assert board.read_all_relays() == [1]

    board.deactivate_relay(relay_index=1)
    assert not board.is_relay_active(1)
    assert board.read_all_relays() == []


def test_activate_list():
    board = make_board()
    board.activate_relay(relay_list=[0, 3])
    assert board.read_all_relays() == [0, 3]


def test_activate_already_active_skips_hardware():
    board = make_board()
    board.activate_relay(relay_index=2)
    writes_before = list(board.hw_writes)
    board.activate_relay(relay_index=2)
    assert board.hw_writes == writes_before


def test_toggle():
    board = make_board()
    board.toggle_relay(2)
    assert board.is_relay_active(2)
    board.toggle_relay(2)
    assert not board.is_relay_active(2)


def test_parameter_validation():
    board = make_board()
    with pytest.raises(ValueError):
        board.activate_relay(relay_index=0, relay_list=[1])
    with pytest.raises(ValueError):
        board.activate_relay()
    with pytest.raises(ValueError):
        board.activate_relay(relay_list=[])
    with pytest.raises(IndexError):
        board.activate_relay(relay_index=99)
    with pytest.raises(IndexError):
        board.activate_relay(relay_list=[-1])
    with pytest.raises(IndexError):
        board.toggle_relay(99)


def test_apply_delta_no_change_is_quiet():
    # regression: the no-change path called logger.debug where the module
    # defines LOGGER, so a no-op delta raised NameError
    board = make_board()
    board._apply_delta(set(board.read_all_relays()))
    assert board.hw_writes == []


# ---------------------------------------------------------------- cache semantics

def test_read_all_uses_cache_without_force():
    board = make_board()
    board.activate_relay(relay_index=1)
    assert board.read_all_relays() == [1]
    assert board.read_relay_calls == 0


def test_read_all_force_resyncs_from_hardware():
    board = make_board()
    # hardware changes behind the driver's back
    board.hw_state[2] = 1
    assert board.read_all_relays() == []          # cache is stale
    assert board.read_all_relays(force=True) == [2]
    assert board.read_relay_calls == board.num_relays
    assert board.read_all_relays() == [2]         # cache resynced


def test_write_all_relays():
    board = make_board()
    board.write_all_relays([0, 2])
    assert board.read_all_relays() == [0, 2]
    board.write_all_relays([])
    assert board.read_all_relays() == []
    with pytest.raises(IndexError):
        board.write_all_relays([99])


# ---------------------------------------------------------------- groups

def test_exclusive_group():
    board = make_board(relay_groups=group_config(
        {"A": RelayGroupType.EXCLUSIVE}, {0: "A", 2: "A"}))

    board.activate_relay(relay_index=0)
    assert board.read_all_relays() == [0]

    board.activate_relay(relay_index=2)   # selection swaps
    assert board.read_all_relays() == [2]

    with pytest.raises(ValueError):
        board.activate_relay(relay_list=[0, 2])

    with pytest.raises(ValueError):
        board.write_all_relays([0, 2])

    board.write_all_relays([0])
    assert board.read_all_relays() == [0]


def test_force_matching_group():
    board = make_board(relay_groups=group_config(
        {"B": RelayGroupType.FORCE_MATCHING}, {0: "B", 1: "B"}))

    board.activate_relay(relay_index=0)
    assert board.read_all_relays() == [0, 1]

    board.deactivate_relay(relay_index=1)
    assert board.read_all_relays() == []

    board.toggle_relay(0)
    assert board.read_all_relays() == [0, 1]
    board.toggle_relay(1)
    assert board.read_all_relays() == []


def test_check_matching_group():
    board = make_board(relay_groups=group_config(
        {"C": RelayGroupType.CHECK_MATCHING}, {0: "C", 1: "C", 2: "C"}))

    with pytest.raises(ValueError):
        board.activate_relay(relay_index=0)

    board.activate_relay(relay_list=[0, 1, 2])
    assert board.read_all_relays() == [0, 1, 2]

    with pytest.raises(ValueError):
        board.deactivate_relay(relay_list=[0, 1])

    with pytest.raises(ValueError):
        board.toggle_relay(0)

    board.deactivate_relay(relay_list=[0, 1, 2])
    assert board.read_all_relays() == []


def test_synced_group():
    board = make_board(relay_groups=group_config(
        {"S": RelayGroupType.SYNCED}, {0: "S", 1: "S", 2: "S"}))

    with pytest.raises(ValueError):
        board.activate_relay(relay_index=0)

    with pytest.raises(ValueError):
        board.toggle_relay(0)

    board.activate_relay(relay_list=[0, 1, 2])
    assert board.read_all_relays() == [0, 1, 2]

    # write_all is a full-group update by definition: mixed state allowed
    board.write_all_relays([1])
    assert board.read_all_relays() == [1]


def test_mixed_group_and_ungrouped():
    board = make_board(relay_groups=group_config(
        {"B": RelayGroupType.FORCE_MATCHING}, {0: "B", 1: "B"}))

    board.write_all_relays([0, 2])   # group coerces to {0,1}, keeps 2
    assert board.read_all_relays() == [0, 1, 2]

    board.write_all_relays([2])
    assert board.read_all_relays() == [2]


def test_cross_group_targets_rejected():
    board = make_board(relay_groups=group_config(
        {"A": RelayGroupType.EXCLUSIVE, "B": RelayGroupType.FORCE_MATCHING},
        {0: "A", 1: "A", 2: "B", 3: "B"}))
    with pytest.raises(ValueError):
        board.activate_relay(relay_list=[0, 2])


# ---------------------------------------------------------------- auto off

def test_auto_off_nonblocking_fires():
    # regression: the timer callback held the non-reentrant SeqGuard and
    # then called deactivate_relay (which re-acquires it), so the relay
    # never came back off
    board = make_board()
    board.activate_relay(relay_index=0, auto_off_ms=30)
    assert board.is_relay_active(0)

    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline and board.is_relay_active(0):
        time.sleep(0.01)

    assert not board.is_relay_active(0), "auto_off timer never deactivated the relay"


def test_auto_off_blocking():
    # regression trio: 'time' was not imported, the sleep got milliseconds
    # (1000x too long) and the deactivate referenced an undefined variable
    board = make_board()
    t0 = time.monotonic()
    board.activate_relay(relay_index=1, auto_off_ms=40, blocking=True)
    elapsed = time.monotonic() - t0

    assert not board.is_relay_active(1)
    assert 0.03 <= elapsed < 2.0, f"blocking auto-off took {elapsed:.3f}s"


# ---------------------------------------------------------------- seq guard

def test_seq_delay_spaces_operations():
    board = make_board(seq_delay_ms=60)
    board.activate_relay(relay_index=0)
    t0 = time.monotonic()
    board.deactivate_relay(relay_index=0)
    elapsed_ms = (time.monotonic() - t0) * 1000.0
    assert elapsed_ms >= 45, f"second op ran after only {elapsed_ms:.1f} ms"


# ---------------------------------------------------------------- lifecycle

def test_deactivate_all():
    board = make_board()
    board.activate_relay(relay_list=[0, 3])
    board.deactivate_all()
    assert board.read_all_relays() == []
    assert ("off", 0) in board.hw_writes
    assert ("off", 3) in board.hw_writes


def test_close_is_idempotent():
    board = make_board()
    board.close()
    board.close()
    assert board._closed


def test_context_manager_closes():
    with make_board() as board:
        board.activate_relay(relay_index=0)
    assert board._closed


# ---------------------------------------------------------------- named wrappers

def test_named_relay():
    board = make_board()
    r1 = NamedRelay(board_name="fake", board=board, index=1, name="mains")
    r1.activate()
    assert r1.is_active()
    r1.toggle()
    assert not r1.is_active()
    r1.activate()
    r1.deactivate()
    assert board.read_all_relays() == []


def test_named_relay_group_exclusive():
    board = make_board(relay_groups=group_config(
        {"A": RelayGroupType.EXCLUSIVE}, {0: "A", 2: "A"}))
    group = NamedRelayGroup(
        board_name="fake",
        board=board,
        name="A",
        members=[0, 2],
        gtype=RelayGroupType.EXCLUSIVE,
        name_to_index={"R0": 0, "R2": 2},
    )
    group.activate_exclusive("R0")
    assert board.read_all_relays() == [0]
    group.activate_exclusive("R2")
    assert board.read_all_relays() == [2]

    with pytest.raises(KeyError):
        group.activate_exclusive("nope")


def test_named_relay_group_synced_update():
    board = make_board(relay_groups=group_config(
        {"S": RelayGroupType.SYNCED}, {0: "S", 1: "S", 2: "S"}))
    group = NamedRelayGroup(
        board_name="fake",
        board=board,
        name="S",
        members=[0, 1, 2],
        gtype=RelayGroupType.SYNCED,
        name_to_index={"R0": 0, "R1": 1, "R2": 2},
    )
    group.update_group(["R0", "R2"])
    assert board.read_all_relays() == [0, 2]
    group.update_group([])
    assert board.read_all_relays() == []
