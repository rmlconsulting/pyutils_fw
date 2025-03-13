
import logging
import os
import sys
import time

# add parent directory to python path for this example
this_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.abspath(os.path.join(this_dir, '..'))
print(f"parent_dir = {parent_dir}")
sys.path.insert(0, parent_dir)

import jlink_device

##########################################
# LOGGING
##########################################
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s-%(name)s-%(levelname)s:%(message)s"
)
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())
logger.setLevel(logging.DEBUG)

##########################################
# device setup
##########################################
# some example device configs
config = jlink_device.JLinkTransportConfig( "NRF52832_XXAA" )
#config = jlink_device.JLinkTransportConfig( "STM32G491VE", speed=5000 )

device = jlink_device.JLinkComms(config)

##########################################
# run test
##########################################
device.start_capturing_traces()

# some example button info
success, traces, remaining_search = device.wait_for_trace("Button (?P<button_num>\d+) pressed", timeout_ms = 10000)

print(f"my trace. successful:{success}. value:{traces}")

##########################################
# shutdown
##########################################
device.stop_capturing_traces()

