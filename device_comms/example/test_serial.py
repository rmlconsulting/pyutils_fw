
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
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())
logger.setLevel(logging.DEBUG)

config = serial_device.SerialCommsDeviceConfig(
                            serial_device_path = "/dev/tty.usbmodem1101",
                            baud_rate = 115200)

device = serial_device.SerialCommsDevice(config)

device.start_capturing_traces()

foo = device.wait_for_trace("STEERING", timeout_ms = 5000)

print(foo)

print("###############################\nSLEEEEEEEEP 2\n#########################\n\n")
time.sleep(2)

device.send_cmd("?")
foo = device.wait_for_trace("write_pin", accumulate_traces=True)
print(foo)

device.send_cmd_to_link_management("halt")

device.stop_capturing_traces()

