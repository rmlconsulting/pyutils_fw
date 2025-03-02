
import jlink_device
import logging
import time

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

devices = device.get_device_list()
print(devices)



##########################################
# run test
##########################################
device.start_capturing_traces()
foo = device.wait_for_trace("STEERING", timeout_ms = 5000)

print(foo)

##########################################
# shutdown
##########################################
device.stop_capturing_traces()

