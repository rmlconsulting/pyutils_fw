from NumatoRelayBoard import NumatoDevice
import time

board = NumatoDevice(path = "/dev/tty.usbmodem31324301")

for i in range(0,board.num_relays):
    board.set("relay", i)

time.sleep(1)

for i in range(0, board.num_relays):
    board.clear("relay", i)

