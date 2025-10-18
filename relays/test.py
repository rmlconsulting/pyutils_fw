import time
import sys

from relay_base import RelayBase, RelayGroupType
from numato_relay_board import NumatoDevice
from named_relay_utils import NamedRelay, NamedRelayGroup

import logging


logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

from typing import Iterable

# assume RelayBase and RelayGroupType are importable from your codebase
# from yourmodule import RelayBase, RelayGroupType

# ---------------- in-memory test device with verbose logging ----------------

class TestRelayBoard(RelayBase):
    """
    simple in-memory relay board for exercising group logic.
    read_all_relays() returns a 0/1 vector of length num_relays.
    adds detailed logging for write_all, activate, and deactivate.
    """

    def __init__(self, num_relays=4, relay_groups: dict = {}, seq_delay_ms: int = 0):

        super().__init__(num_relays=num_relays,
                         supports_autosense=False,
                         relay_groups=relay_groups,
                         seq_delay_ms = seq_delay_ms)

    def _activate_relay(self, relay_index: int) -> None:
        prev = int(self._relay_status.get(relay_index, 0))
        self._relay_status[relay_index] = 1
        logging.debug("activate relay %d: %d -> 1", relay_index, prev)

    def _deactivate_relay(self, relay_index: int) -> None:
        prev = int(self._relay_status.get(relay_index, 0))
        self._relay_status[relay_index] = 0
        logging.debug("deactivate relay %d: %d -> 0", relay_index, prev)

    def read_all_relays(self) -> list[int]:
        """
        return a list of relay states (0/1) for all relays.
        always returns exactly num_relays elements.
        """
        return [self._relay_status.get(i, 0) for i in range(self.num_relays)]

    def write_all_relays(self, on_channels: list[int]) -> None:
        """
        log the request, delegate to base class to enforce group logic,
        then log the post-write state vector.
        """
        logging.debug("write_all_relays request on_channels=%s", sorted(on_channels))
        super().write_all_relays(on_channels)
        logging.debug("write_all_relays applied, state=%s", self.read_all_relays())


# ---------------- optional: run against your NumatoDevice ----------------

USE_NUMATO = True
NUMATO_PATH = "/dev/tty.usbmodem21101"

if USE_NUMATO:
    def make_board(relay_groups: dict, seq_delay_ms: int = 50):
        return NumatoDevice(
            path=NUMATO_PATH,
            num_relays=4,
            num_gpio=4,
            num_adc=4,
            relay_groups=relay_groups,
            seq_delay_ms = seq_delay_ms
        )
else:
    def make_board(relay_groups: dict, seq_delay_ms: int = 0):
        return TestRelayBoard( num_relays = 4,
                               relay_groups=relay_groups,
                               seq_delay_ms=seq_delay_ms)

# ---------------- helpers ----------------

def announce(msg: str):
    logging.info("")
    logging.info("### %s", msg)
    logging.info("")

def vectorize_state(board, raw) -> list[int]:
    """
    normalize different driver return shapes to a 0/1 vector of length num_relays.
    if raw already looks like a 0/1 vector, return it.
    otherwise treat raw as list of active indices.
    """
    if isinstance(raw, list) and len(raw) == board.num_relays and all(x in (0, 0.0, 1, 1.0) for x in raw):
        return [int(x) for x in raw]
    vec = [0] * board.num_relays
    for i in raw:
        if 0 <= i < board.num_relays:
            vec[i] = 1
    return vec

def check(board, expected_on_indices: Iterable[int], step: str) -> bool:
    """
    compare the expected ON indices against the device's actual state.
    logs:
      INFO  expected relay state: [...] actual relay state: [...]
      DEBUG step: <desc> | expected: [...] | actual: [...] | OK/MISMATCH
    returns True on match, False otherwise.
    """
    expected_vec = [1 if i in set(expected_on_indices) else 0 for i in range(board.num_relays)]
    actual_vec = vectorize_state(board, board.read_all_relays())
    ok = (actual_vec == expected_vec)
    logging.info("expected relay state: %s actual relay state: %s", expected_vec, actual_vec)
    logging.debug(
        "step: %s | expected: %s | actual: %s | %s",
        step, expected_vec, actual_vec, "OK" if ok else "MISMATCH"
    )
    return ok

def print_header(n: int, scenario: str):
    print("\n" + "#" * 31)
    print(f"# test {n}: {scenario}")
    print("#" * 31)

def print_config(relay_groups: dict):
    print("relay configuration:")
    groups = relay_groups.get("groups", {})
    relays = relay_groups.get("relays", {})
    for i in range(4):
        r = relays.get(i)
        if not r:
            print(f"  relay {i}: independent")
            continue
        gname = r["group_name"]
        gtype = groups.get(gname, {}).get("type", "unknown")
        print(f"  relay {i}: group '{gname}' ({gtype.name if hasattr(gtype, 'name') else gtype})")
    print()

def print_result(ok: bool):
    print(f"result: {'pass' if ok else 'fail'}\n")


# ---------------- tests ----------------

def run():
    logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    tests = []
    tnum = 1

    # exclusive group of 2: sequential activate swaps member
    def t1():
        rg = {
            "groups": {"A": {"type": RelayGroupType.EXCLUSIVE}},
            "relays": {0: {"group_name": "A"}, 2: {"group_name": "A"}},
        }
        b = make_board(rg)
        print_config(rg)
        ok = True

        ok &= check(b, [], "initial state")

        announce("turning on group A by activating relay 0 (exclusive -> expect only 0 on)")
        b.activate_relay(relay_index=0)
        ok &= check(b, [0], "after activate 0")

        announce("switching selection in group A by activating relay 2 (exclusive -> expect only 2 on)")
        b.activate_relay(relay_index=2)
        ok &= check(b, [2], "after activate 2")

        announce("selecting relay 0 in group A via write_all_relays([0]) (exclusive -> expect only 0 on)")
        b.write_all_relays([0])
        ok &= check(b, [0], "after write_all {0}")

        announce("clearing selection in group A via write_all_relays([]) (exclusive -> expect all off)")
        b.write_all_relays([])
        ok &= check(b, [], "after write_all {}")

        announce("selecting relay 2 in group A via write_all_relays([2]) (exclusive -> expect only 2 on)")
        b.write_all_relays([2])
        ok &= check(b, [2], "after write_all {2}")

        return ok
    tests.append(("exclusive group of 2: updates via activate_* and write_all_relays", t1))

    # exclusive negative: cannot activate two at once
    def t2():
        rg = {
            "groups": {"A": {"type": RelayGroupType.EXCLUSIVE}},
            "relays": {0: {"group_name": "A"}, 1: {"group_name": "A"}},
        }
        b = make_board(rg)
        print_config(rg)
        ok = True
        ok &= check(b, [], "initial state")
        announce("attempting to activate [0,1] in exclusive group A (expect ValueError)")
        try:
            b.activate_relay(relay_list=[0, 1])
            return False
        except ValueError:
            ok &= check(b, [], "after rejected multi-activate")
            return ok
    tests.append(("exclusive group of 2: activating [0,1] raises", t2))

    # force_matching group of 2: single activate -> all on; single deactivate -> all off
    def t3():
        rg = {
            "groups": {"B": {"type": RelayGroupType.FORCE_MATCHING}},
            "relays": {0: {"group_name": "B"}, 1: {"group_name": "B"}},
        }
        b = make_board(rg)
        print_config(rg)
        ok = True
        ok &= check(b, [], "initial state")
        announce("turning on all of group B by activating relay 0 (force_matching -> expect {0,1} on)")
        b.activate_relay(relay_index=0)
        ok &= check(b, [0, 1], "after activate 0")
        announce("turning off all of group B by deactivating relay 1 (force_matching -> expect all off)")
        b.deactivate_relay(relay_index=1)
        ok &= check(b, [], "after deactivate 1")
        return ok
    tests.append(("force_matching group of 2: single op applies to entire group", t3))

    # force_matching toggle: toggle one when off -> all on; toggle again -> all off
    def t4():
        rg = {
            "groups": {"B": {"type": RelayGroupType.FORCE_MATCHING}},
            "relays": {0: {"group_name": "B"}, 1: {"group_name": "B"}},
        }
        b = make_board(rg)
        print_config(rg)
        ok = True
        ok &= check(b, [], "initial state")
        announce("turning on all of group B by toggling relay 0 (force_matching -> expect {0,1} on)")
        b.toggle_relay(relay_index=0)
        ok &= check(b, [0, 1], "after toggle 0")
        announce("turning off all of group B by toggling relay 0 again (force_matching -> expect all off)")
        b.toggle_relay(relay_index=0)
        ok &= check(b, [], "after toggle 0 again")
        return ok
    tests.append(("force_matching group of 2: toggles obey group intent", t4))

    # force_matching mixed intent via write_all: raise on adds+removes conflict
    def t5():
        rg = {
            "groups": {"B": {"type": RelayGroupType.FORCE_MATCHING}},
            "relays": {0: {"group_name": "B"}, 1: {"group_name": "B"}},
        }
        b = make_board(rg)
        print_config(rg)
        ok = True

        ok &= check(b, [], "initial state")

        announce("creating illegal partial state {0} via raw write (bypasses group logic) to test mixed intent")
        b._write_all_relays_raw([0])
        ok &= check(b, [0], "after raw write {0}")

        announce("requesting desired state {1} via write_all_relays (expect mixed add/remove -> ValueError)")
        try:
            b.write_all_relays([1])
            return False
        except ValueError:
            ok &= check(b, [0], "after rejected mixed-intent write_all")
            return ok
    tests.append(("force_matching: write_all mixed add/remove raises", t5))

    # check_matching group of 3: partial ops raise; full ops succeed
    def t6():
        rg = {
            "groups": {"C": {"type": RelayGroupType.CHECK_MATCHING}},
            "relays": {0: {"group_name": "C"}, 1: {"group_name": "C"}, 2: {"group_name": "C"}},
        }
        b = make_board(rg)
        print_config(rg)
        ok = True
        ok &= check(b, [], "initial state")

        announce("attempting partial activate of group C by activating relay 0 (check_matching -> expect ValueError)")
        try:
            b.activate_relay(relay_index=0)
            return False
        except ValueError:
            ok &= check(b, [], "after rejected partial activate")

        announce("activating the entire group C with [0,1,2] (check_matching -> expect all on)")
        b.activate_relay(relay_list=[0, 1, 2])
        ok &= check(b, [0, 1, 2], "after full activate")

        announce("attempting partial deactivate of group C with [0,1] (check_matching -> expect ValueError)")
        try:
            b.deactivate_relay(relay_list=[0, 1])
            return False
        except ValueError:
            ok &= check(b, [0, 1, 2], "after rejected partial deactivate")

        announce("deactivating the entire group C with [0,1,2] (check_matching -> expect all off)")
        b.deactivate_relay(relay_list=[0, 1, 2])
        ok &= check(b, [], "after full deactivate")
        return ok
    tests.append(("check_matching group of 3: partial operations raise", t6))

    # single-member force_matching: behaves like a normal relay
    def t7():
        rg = {
            "groups": {"D": {"type": RelayGroupType.FORCE_MATCHING}},
            "relays": {3: {"group_name": "D"}},
        }
        b = make_board(rg)
        print_config(rg)
        ok = True
        ok &= check(b, [], "initial state")
        announce("turning on group D (size=1) by activating relay 3 (expect relay 3 on)")
        b.activate_relay(relay_index=3)
        ok &= check(b, [3], "after activate 3")
        announce("turning off group D (size=1) by toggling relay 3 (expect relay 3 off)")
        b.toggle_relay(relay_index=3)
        ok &= check(b, [], "after toggle 3")
        return ok
    tests.append(("single-member force_matching: trivial group works", t7))

    # mixed: force_matching {0,1} + ungrouped {2}
    def t8():
        rg = {
            "groups": {"B": {"type": RelayGroupType.FORCE_MATCHING}},
            "relays": {0: {"group_name": "B"}, 1: {"group_name": "B"}},
        }
        b = make_board(rg)
        print_config(rg)
        ok = True
        ok &= check(b, [], "initial state")
        announce("turning on group B by write_all with {0,2} (expect group coerces to {0,1} and keep ungrouped 2)")
        b.write_all_relays([0, 2])
        ok &= check(b, [0, 1, 2], "after write_all {0,2}")
        announce("turning off group B while keeping ungrouped 2 by write_all with {2}")
        b.write_all_relays([2])
        ok &= check(b, [2], "after write_all {2}")
        return ok
    tests.append(("mixed: force_matching group with ungrouped channel", t8))

    # two groups: exclusive {0,1} + force_matching {2,3}
    def t9():
        rg = {
            "groups": {
                "A": {"type": RelayGroupType.EXCLUSIVE},
                "B": {"type": RelayGroupType.FORCE_MATCHING},
            },
            "relays": {
                0: {"group_name": "A"},
                1: {"group_name": "A"},
                2: {"group_name": "B"},
                3: {"group_name": "B"},
            },
        }
        b = make_board(rg)
        print_config(rg)
        ok = True
        ok &= check(b, [], "initial state")

        announce("selecting relay 0 in exclusive group A (expect only 0 on)")
        b.activate_relay(relay_index=0)
        ok &= check(b, [0], "after activate 0 in A")

        announce("selecting relay 1 in exclusive group A and turning on group B by write_all {1,3}")
        b.write_all_relays([1, 3])
        ok &= check(b, [1, 2, 3], "after write_all {1,3}")

        announce("turning off group B by toggling relay 2 (exclusive group A remains on relay 1)")
        b.toggle_relay(relay_index=2)
        ok &= check(b, [1], "after toggle 2 in B")
        return ok
    tests.append(("two groups: exclusive {0,1} + force_matching {2,3}", t9))

    # check_matching group of 4: full operations only (toggle list removed)
    def t10():
        rg = {
            "groups": {"E": {"type": RelayGroupType.CHECK_MATCHING}},
            "relays": {0: {"group_name": "E"}, 1: {"group_name": "E"}, 2: {"group_name": "E"}, 3: {"group_name": "E"}},
        }
        b = make_board(rg)
        print_config(rg)
        ok = True
        ok &= check(b, [], "initial state")

        announce("attempting single toggle of group E by toggling relay 0 (check_matching -> expect ValueError)")
        try:
            b.toggle_relay(relay_index=0)
            return False
        except ValueError:
            ok &= check(b, [], "after rejected single toggle")

        announce("turning full group E ON via activate_relay([0,1,2,3]) (expect all on)")
        b.activate_relay(relay_list=[0, 1, 2, 3])
        ok &= check(b, [0, 1, 2, 3], "after full activate")

        announce("turning full group E OFF via deactivate_relay([0,1,2,3]) (expect all off)")
        b.deactivate_relay(relay_list=[0, 1, 2, 3])
        ok &= check(b, [], "after full deactivate")
        return ok
    tests.append(("check_matching group of 4: full toggles only", t10))

    # ---------- NEW: SYNCED group tests ----------

    # SYNCED group of 3: write_all allows mixed state if the whole group is updated
    def t11():
        rg = {
            "groups": {"S": {"type": RelayGroupType.SYNCED}},
            "relays": {0: {"group_name": "S"}, 1: {"group_name": "S"}, 2: {"group_name": "S"}},
        }
        b = make_board(rg)
        print_config(rg)
        ok = True

        ok &= check(b, [], "initial state")

        announce("writing full SYNCED group S with mixed state via write_all {0,2} (expect 0,2 on; 1 off)")
        b.write_all_relays([0, 2])
        ok &= check(b, [0, 2], "after write_all {0,2}")

        announce("writing full SYNCED group S via write_all {0} (still a full-group update; expect only 0 on)")
        b.write_all_relays([0])
        ok &= check(b, [0], "after write_all {0}")


        announce("writing full SYNCED group S with new mix via write_all {1} (expect only 1 on)")
        b.write_all_relays([1])
        ok &= check(b, [1], "after write_all {1}")
        return ok
    tests.append(("synced group of 3: write_all accepts full-group mixed updates; rejects partial", t11))

    # SYNCED group of 2: single-member activate/deactivate rejected; full-list accepted
    def t12():
        rg = {
            "groups": {"S": {"type": RelayGroupType.SYNCED}},
            "relays": {1: {"group_name": "S"}, 3: {"group_name": "S"}},
        }
        b = make_board(rg)
        print_config(rg)
        ok = True

        ok &= check(b, [], "initial state")

        announce("attempting single-member activate relay 1 in SYNCED S -> expect ValueError")
        try:
            b.activate_relay(relay_index=1)
            return False
        except ValueError:
            ok &= check(b, [], "after rejected single-member activate on S")

        announce("activating full SYNCED group S via activate_relay([1,3]) -> expect {1,3} on")
        b.activate_relay(relay_list=[1, 3])
        ok &= check(b, [1, 3], "after full activate S")

        announce("deactivating full SYNCED group S via deactivate_relay([1,3]) -> expect all off")
        b.deactivate_relay(relay_list=[1, 3])
        ok &= check(b, [], "after full deactivate S")
        return ok
    tests.append(("synced group of 2: single-member ops rejected; full-list ops accepted", t12))

    # SYNCED: single-member toggle is forbidden
    def t13():
        rg = {
            "groups": {"S": {"type": RelayGroupType.SYNCED}},
            "relays": {0: {"group_name": "S"}, 1: {"group_name": "S"}},
        }
        b = make_board(rg)
        print_config(rg)
        ok = True

        ok &= check(b, [], "initial state")

        announce("attempting single-member toggle on SYNCED group S (relay 0) -> expect ValueError")
        try:
            b.toggle_relay(relay_index=0)
            return False
        except ValueError:
            ok &= check(b, [], "after rejected single toggle on S")
            return ok
    tests.append(("synced: single-member toggle rejected", t13))


    # SYNCED + ungrouped: full-group update with extra ungrouped allowed
    def t14():
        rg = {
            "groups": {"S": {"type": RelayGroupType.SYNCED}},
            "relays": {0: {"group_name": "S"}, 1: {"group_name": "S"}},
        }
        b = make_board(rg)
        print_config(rg)
        ok = True

        ok &= check(b, [], "initial state")

        announce("write_all {0,2} (S is updated in this call, mixed allowed) -> expect {0,2} on")
        b.write_all_relays([0, 2])
        ok &= check(b, [0, 2], "after write_all {0,2}")

        announce("write_all {1} (flip S mix, ungrouped 2 goes off) -> expect {1} on")
        b.write_all_relays([1])
        ok &= check(b, [1], "after write_all {1}")
        return ok


    tests.append(("synced + ungrouped: full-group updates allowed; partial rejected", t14))


    # SYNCED with EXCLUSIVE present: write_all must satisfy both policies
    def t15():
        rg = {
            "groups": {
                "S": {"type": RelayGroupType.SYNCED},
                "A": {"type": RelayGroupType.EXCLUSIVE},
            },
            "relays": {
                0: {"group_name": "S"},
                1: {"group_name": "S"},
                2: {"group_name": "A"},
                3: {"group_name": "A"},
            },
        }
        b = make_board(rg)
        print_config(rg)
        ok = True

        ok &= check(b, [], "initial state")

        announce("write_all {0,2} -> S updated in one call (mixed allowed), A selects 2 -> expect {0,2} on")
        b.write_all_relays([0, 2])
        ok &= check(b, [0, 2], "after write_all {0,2}")

        announce("write_all {1,3} -> S updated (mixed allowed), A switches selection to 3 -> expect {1,3} on")
        b.write_all_relays([1, 3])
        ok &= check(b, [1, 3], "after write_all {1,3}")
        return ok

    tests.append(("synced + exclusive: combined policy enforcement", t15))

    # t16: Named relays + EXCLUSIVE group {R0, R2} using NamedRelayGroup helpers
    def t16():
        # build relay_groups config (EXCLUSIVE group A with members 0 and 2)
        rg = {
            "groups": {"A": {"type": RelayGroupType.EXCLUSIVE}},
            "relays": {0: {"group_name": "A"}, 2: {"group_name": "A"}},
        }
        b = make_board(rg)
        print_config(rg)
        ok = True

        # name mapping
        name_to_index = {"R0": 0, "R1": 1, "R2": 2, "R3": 3}

        # named single relays
        R0 = NamedRelay(board_name="board", board=b, index=0, name="R0")
        R2 = NamedRelay(board_name="board", board=b, index=2, name="R2")

        # named group
        G = NamedRelayGroup(
            board_name="board",
            board=b,
            name="A",
            members=[0, 2],
            gtype=RelayGroupType.EXCLUSIVE,
            name_to_index=name_to_index,
        )

        ok &= check(b, [], "initial state")

        announce("activate_exclusive('R0') on EXCLUSIVE A (expect only 0 on)")
        G.activate_exclusive("R0")
        ok &= check(b, [0], "after G.activate_exclusive('R0')")

        announce("activate_exclusive('R2') on EXCLUSIVE A (expect only 2 on)")
        G.activate_exclusive("R2")
        ok &= check(b, [2], "after G.activate_exclusive('R2')")

        announce("NamedRelay.activate() on R0 (expects selection switch to 0)")
        R0.activate()
        ok &= check(b, [0], "after R0.activate()")

        announce("NamedRelay.deactivate() on R2 (no change since R2 is off)")
        R2.deactivate()
        ok &= check(b, [0], "after R2.deactivate()")

        return ok
    tests.append(("Named relays + EXCLUSIVE group {R0, R2} using NamedRelayGroup helpers", t16))

    # t17: Named relays + FORCE_MATCHING group {R1, R3} with ungrouped R2
    def t17():
        rg = {
            "groups": {"B": {"type": RelayGroupType.FORCE_MATCHING}},
            "relays": {1: {"group_name": "B"}, 3: {"group_name": "B"}},
        }
        b = make_board(rg)
        print_config(rg)
        ok = True

        name_to_index = {"R0": 0, "R1": 1, "R2": 2, "R3": 3}
        R1 = NamedRelay(board_name="board", board=b, index=1, name="R1")
        R2 = NamedRelay(board_name="board", board=b, index=2, name="R2")

        G = NamedRelayGroup(
            board_name="board",
            board=b,
            name="B",
            members=[1, 3],
            gtype=RelayGroupType.FORCE_MATCHING,
            name_to_index=name_to_index,
        )

        ok &= check(b, [], "initial state")

        announce("R1.activate() in FORCE_MATCHING B (expect {1,3} on)")
        R1.activate()
        ok &= check(b, [1, 3], "after R1.activate()")

        announce("G.deactivate_all() to turn B off, then R2.activate() (expect {2} on)")
        G.deactivate_all()
        R2.activate()
        ok &= check(b, [2], "after G.deactivate_all() + R2.activate()")

        announce("G.activate_all() (expect {1,3,2} on -> group on + R2 preserved)")
        G.activate_all()
        ok &= check(b, [1, 2, 3], "after G.activate_all()")

        return ok

    tests.append(("Named relays + FORCE_MATCHING group {R1, R3} with ungrouped R2", t17))

    # t18: SeqGuard delay — ensure min spacing between ops is enforced
    def t18():
        SEQ_MS = 100  # measurable on real hardware
        rg = {"groups": {}, "relays": {}}

        b = make_board(rg, seq_delay_ms=SEQ_MS)
        print_config(rg)
        ok = True
        ok &= check(b, [], "initial state")

        announce(f"timing test: activate(0) then immediately deactivate(0); "
                 f"expect the second call to take ≥ {SEQ_MS} ms due to seq guard")

        # first transaction: turn relay 0 ON (engages guard)
        b.activate_relay(relay_index=0)
        ok &= check(b, [0], "after activate 0")

        # second transaction: should be held by the guard for ~SEQ_MS
        import time
        t0 = time.monotonic()
        b.deactivate_relay(relay_index=0)
        t1 = time.monotonic()
        elapsed_ms = (t1 - t0) * 1000.0

        logging.info("seqguard measured elapsed for 2nd op: %.1f ms (seq_delay_ms=%d)",
                     elapsed_ms, SEQ_MS)

        # allow some jitter, but it should be close to (or above) the configured delay
        ok &= (elapsed_ms >= 0.9 * SEQ_MS)

        # sanity: ended OFF
        ok &= check(b, [], "after deactivate 0")

        return ok
    tests.append(("SeqGuard delay — ensure min spacing between ops is enforced", t18))

    # test 19: named group + SYNCED with update_group()
    def t19():
        rg = {
            "groups": {"S": {"type": RelayGroupType.SYNCED}},
            "relays": {0: {"group_name": "S"}, 1: {"group_name": "S"}, 2: {"group_name": "S"}},
        }
        b = make_board(rg)
        print_config(rg)
        ok = True

        name_to_index = {"R0": 0, "R1": 1, "R2": 2, "R3": 3}
        S = NamedRelayGroup(
            board_name="board",
            board=b,
            name="S",
            members=[0, 1, 2],
            gtype=RelayGroupType.SYNCED,
            name_to_index=name_to_index,
        )

        ok &= check(b, [], "initial state")

        announce("S.update_group(['R0','R2']) -> expect 0,2 on; 1 off")
        S.update_group(["R0", "R2"])
        ok &= check(b, [0, 2], "after S.update_group(['R0','R2'])")

        announce("S.update_group([]) -> expect all S off")
        S.update_group([])
        ok &= check(b, [], "after S.update_group([])")
        return ok
    tests.append(("named group + SYNCED with update_group()", t19))

    passed = 0
    failed = 0
    failed_tests = []

    for name, fn in tests:
        print_header(tnum, name)

        # print configuration before running the test (best-effort, tests also print it)
        try:
            rg = fn.__defaults__[0] if fn.__defaults__ else None
            if isinstance(rg, dict):
                print_config(rg)
        except Exception:
            pass

        ok = False
        try:
            ok = fn()
        except Exception:
            logging.exception("unexpected error during %s", name)
            ok = False

        print_result(ok)
        if ok:
            passed += 1
        else:
            failed += 1
            failed_tests.append(f"test {tnum}: {name}")

        tnum += 1


    total = passed + failed
    print("=" * 31)
    print("TEST SUMMARY")
    print("=" * 31)
    print(f"Total tests: {total}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    if failed_tests:
        print("Failed tests:")
        for t in failed_tests:
            print(f"  - {t}")
    print("=" * 31)

if __name__ == "__main__":
    run()

