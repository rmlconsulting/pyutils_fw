# Relays

Relays are great ways to open and close circuits or emulate a button press without introducing a new reference or power source into the target under test.

The following relay board manufacturers are supported:
Numato - All USB variants are officially supported. tested on 1, 4 and 32 relay variants. GPIO and ADC functionality supported as well. See https://numato.com/product-category/automation/relay-modules/

LCUS relays - 1,2,4,8 port variants - see https://a.co/d/45a0DSb

For now, this library targets linux and MacOS. if you want support for windows,
email me at requests@rmlconsulting.dev

### Base Class

Many relay boards will have specific functionality beyond relays, such as ADCs or GPIO control. As this module is trying to focus on relays, the base class only supports relay functionality but many of the concrete classes expose all functionality of the supported boards

activate\_relay( relay\_number: int ) -> None - active the relay
deactivate\_relay( relay\_number: int ) -> None - shut off the relay
toggle\_relay(relay\_number:int )-> None - invert the state of the relay
is\_relay\_active(relay\_number:int)-> Bool
write\_all\_relays( activated\_relays:list[int] ) -> None - set the state of all relays. the relays that are to be activated are supplied. all others are deactivated
read\_all\_relays( ) -> List[int] - get the list of all relays that are active. queried from hardware, if supported.

### Setup
pip install requirements.txt

that's it. now just connect a relay over USB.

If you want support for ethernet interfaced relay modules please send a note to requests@rmlconsulting.dev - let me know the module name you are interested in getting support for

## quick start

Here is the interface in action

```Python
# Note: each file in this repo includes a logger you can configure. you can configure an individual file by file/module name, or globally via:

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

import time
from numato_relay_board import NumatoRelayBoard

board = NumatoRelayBoard( path = "/dev/tty.usbmodem1101", num_relays = 4)

########################################
# Activating relays 1 by 1
########################################
for i in range(0, board.num_relays):
    board.activate_relay(i)

time.sleep(1)

for i in range(0, board.num_relays):
    board.deactivate_relay(i)

########################################
# read and writing all relays
########################################
# read all
active_relays = board.readall_relays()
assert len(active_relays) == 0, "all relays have been deactivated"

# write out all then read back
board.writeall_relays([0, 2])
active_relays = board.readall_relays()
assert len(active_relays) == 2, "not the right num of active relays"

# write out all then read back
board.writeall_relays([1, 3])
active_relays = board.readall_relays()
assert len(active_relays) == 2, "not the right num of active relays"

# shut off all relays by writing all relays with non marked active
board.writeall_relays([])

```

# SUPPORT

For bugs: Report reproduction steps and OS to bugs@rmlconsulting.dev - if you
know how to fix it, please just push a PR

For questions and customization requests: questions@rmlconsulting.dev
