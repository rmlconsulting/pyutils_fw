
from FunctionCaller import *

from EventGeneratorBase import *
import time

def foo(a):
    print("func")


event_generator = FunctionCaller(foo)

event_timing = EventTiming( time_interval_type = IntervalType.INTERVAL_FIXED,
                            fixed_interval_time_ms = 250,
                            is_repeated = True, )



event_coord = EventCoordinator( evt_gen_impl = event_generator,
                                evt_list = [FunctionCaller.SupportedEvents.FUNCTION_CALL],
                                timing_config = event_timing,
                                max_events = 0,
                                evt_gen_signal = None)

event_coord.start()
while(1) :
    time.sleep(1)



