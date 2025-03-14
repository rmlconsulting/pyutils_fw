
import logging
import os
import sys
import time
import signal


# add parent directory to python path for this example
this_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.abspath(os.path.join(this_dir, '..'))
print(f"parent_dir = {parent_dir}")
sys.path.insert(0, parent_dir)

import jlink_device
from device_comms_base import TraceResponseFormat


##########################################
# LOGGING
##########################################
logging.basicConfig(
    level=logging.DEBUG,
    #format="%(asctime)s-%(name)s-%(levelname)s:%(message)s"
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
# Handle ctrl-c
##########################################
#TODO: wait for trace and other high level functions need to monitor shutdown
#      requests as well
#def handle_sigint(signum, frame):
#    print("Received SIGINT (Ctrl+C)! Exiting gracefully.")
#    device.stop_capturing_traces()
#
#    sys.exit(0)
#
#signal.signal(signal.SIGINT, handle_sigint)

##########################################
# run test
##########################################
device.start_capturing_traces()

# some example button info
success, traces, remaining_search = device.wait_for_trace("Button (?P<button_num>\d+) pressed",
                                                          timeout_ms = 5000,
                                                          trace_response_format = TraceResponseFormat.PROCESSED_RESPONSES)

print(f"my trace. successful:{success}. value:{traces}")

##########################################
# shutdown
##########################################
device.stop_capturing_traces()

