
import logging
import os
import sys
import time

# add parent directory to python path for this example
parent_dir = os.path.abspath(os.path.join(os.getcwd(), '..'))
sys.path.insert(0, parent_dir)

import jlink_device

##########################################
# LOGGING
##########################################
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())
logger.setLevel(logging.DEBUG)

##########################################
# device setup
##########################################
config = jlink_device.JLinkTransportConfig( "NRF52832_XXAA" )

device = jlink_device.JLinkComms(config)

##########################################
# run test
##########################################
device.start_capturing_traces()

success, traces, remaining_search = device.wait_for_trace("my trace: (\d+)", timeout_ms = 5000)

print(f"my trace. successful:{success}. value:{}")

##########################################
# shutdown
##########################################
device.stop_capturing_traces()

