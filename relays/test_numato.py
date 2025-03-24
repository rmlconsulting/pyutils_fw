from numato_relay_board import NumatoDevice, NumatoNode
import time

board = NumatoDevice(path = "/dev/tty.usbmodem1101", num_relays = 4)

# using set / clear functions
for i in range(0,board.num_relays):
    board.set(NumatoNode.relay, i)

time.sleep(1)

for i in range(0, board.num_relays):
    board.clear(NumatoNode.relay, i)

time.sleep(1)

# using activate_relay and deactivate_relay
for i in range(0,board.num_relays):
    board.activate_relay(i)

time.sleep(1)

for i in range(0, board.num_relays):
    board.deactivate_relay(i)

time.sleep(1)

board.writeall(NumatoNode.relay, [1,3])
active_relays = sorted( board.readall(NumatoNode.relay) )
print(f"expecting 1 3 active: {active_relays}")
assert len(active_relays) == 2, "not the right num of active relays"
assert active_relays[0] == 1
assert active_relays[1] == 3
time.sleep(1)
board.writeall(NumatoNode.relay, [0,2])
active_relays = sorted( board.readall(NumatoNode.relay) )
print(f"expecting 0 2 active: {active_relays}")
assert len(active_relays) == 2, "not the right num of active relays"
assert active_relays[0] == 0
assert active_relays[1] == 2
time.sleep(1)
board.writeall()
active_relays = sorted( board.readall(NumatoNode.relay) )
print(f"expecting none active: {board.readall(NumatoNode.relay)}")
assert len(active_relays) == 0, "not the right num of active relays"

