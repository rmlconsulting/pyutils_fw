
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
    format="%(asctime)s_%(name)s_%(levelname)s_%(message)s"
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

'''
2025-03-08 19:28:11,700 - jlink_device - DEBUG - [00:00:02.647,000] <info> app: new battery reading: 16382 mV. last reported: 0mV. sig? 1
2025-03-08 19:28:13,857 - jlink_device - DEBUG - [00:00:04.850,000] <info> app: Button 0 pressed
2025-03-08 19:28:14,052 - jlink_device - DEBUG - [00:00:05.056,000] <info> app: Button 0 released
2025-03-08 19:28:14,385 - jlink_device - DEBUG - [00:00:05.403,000] <info> app: Button 0 pressed
2025-03-08 19:28:14,577 - jlink_device - DEBUG - [00:00:05.596,000] <info> app: Button 0 released
'''

success, traces, remaining_search = device.wait_for_trace("Button (?P<button_num>\d+) pressed", timeout_ms = 5000)

print(f"my trace. successful:{success}. value:{traces}")
success, traces, remaining_search = device.wait_for_trace("Button (?P<button_num>\d+) pressed", timeout_ms = 5000)
print(f"my trace. successful:{success}. value:{traces}")


##########################################
# shutdown
##########################################
device.stop_capturing_traces()

