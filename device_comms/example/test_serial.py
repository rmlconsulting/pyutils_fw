
import logging
import time
import os
import sys

# add parent directory to python path for this example
parent_dir = os.path.abspath(os.path.join(os.getcwd(), '..'))
sys.path.insert(0, parent_dir)

import serial_device

logging.basicConfig(
    level=logging.DEBUG,
#    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())
logger.setLevel(logging.DEBUG)

config = serial_device.SerialCommsDeviceConfig(
                            serial_device_path = "/dev/tty.usbmodem1101",
                            baud_rate = 115200)

device = serial_device.SerialCommsDevice(config)

device.start_capturing_traces()

foo = device.wait_for_trace( cmd = "version",
                             required_responses = r"VERSION:\s*v(?P<version_major>\d+)\.(?P<version_minor>\d+)\.(?P<version_patch>\d+)",
                             timeout_ms = 4000)

print(foo)
assert foo[0], "failed"

print("###############################\n stop\n#########################\n\n")

device.stop_capturing_traces()
print("###############################\n start  \n#########################\n\n")
device.start_capturing_traces()
print("###############################\n stop\n#########################\n\n")
device.stop_capturing_traces()

