import logging
from stdout_capture import StdoutCapture

##########################################
# LOGGING
##########################################
# for lots of logging uncomment this block
#logging.basicConfig(
#    level=logging.DEBUG,
#    #format="%(asctime)s-%(name)s-%(levelname)s:%(message)s"
#)

# for logging in this file, uncomment this block
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())
logger.setLevel(logging.DEBUG)

StdoutCapture(".")

print("foo")

