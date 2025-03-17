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

# everything printed to stdout after this will go to the log file
capture_obj = StdoutCapture(".")

print("foo")
# foo should now be in the logs

# everything printed to stdout after this will go to the new_log file
capture_obj.log_to_new_file("new_log")

print("bar")

