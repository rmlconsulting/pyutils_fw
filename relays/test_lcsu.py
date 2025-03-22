from LCUSRelay import LCUSRelayBoard
import time

relay = LCUSRelayBoard( path = "/dev/tty.usbserial-3132430", num_relays=2)

relay.relay_activate(0)
relay.relay_activate(1)
time.sleep(1)
relay.relay_deactivate(0)
relay.relay_deactivate(1)


