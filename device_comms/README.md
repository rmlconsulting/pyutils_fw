# DeviceComms

The DeviceComms library allows you to open up a comms channel with hardware
devices to the end goal of being able to easily use the data streams coming
they produce.

Ultimately, both ascii and binary interfaces will be supported, but at this
time, only ascii interfaces are supported. stay tuned.

For now, this library targets linux and MacOS. if you want support for windows,
email me at ryan@rmlconsulting.dev

### Design Goals

The top design goals are as follows:

1. Quickly go from cloning this repo -> talking to your target hardware
2. Enable communications over Serial, Jlink and websockets
3. Handle all of the OS-level interactions and thread/process synchronization required to communicate with embedded devices.
4. Provide interfaces that enable meaningful interactions out of the box. the target interactions are:
   - automating development processes
   - automated test interactions
   - manufacturing test scripts
   - easily connect your own GUI to Device Comms objects for graphing or other custom GUIs

### Major Interfaces
I will introduce the major interfaces here but they are best understood through examples below.

The major programmatic interfaces are:
A. message based command / response
B. custom event based command / response
C. message queue interactions to safely grab unprocessed data

The layering of these interfaces are arranged as in the following diagram:

![alt text](interface_diagram.jpeg "Title")

In order to dive into examples lets get setup first.

### Setup
pip install requirements.txt

that's it. now just connect a device over serial, jtag (jlink only), websocket (connect it to your local network).

## quick start

We will do these examples with a serial device, but after the instantiation, all functions extend a common base class and therefore share the same core functionality.

```Python
# Create a Device Comms config object. For now, just be aware each transport layer has its own config struct.

# each file in this repo includes a logger you can configure. i'll place one here so we see lots of data.

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

from serial_device import *

config = SerialCommsDeviceConfig( serial_device_path = "/dev/tty.usbmodem123",
                                  baud_rate = 115200)

device = SerialCommsDevice( config )

device.start_capturing_traces()

# now you should have an active interface you can get traces (i.e. device logs) and send commands to.

```

## Interface 1: The message Interface Parameters

Interacting with the message interface is pretty simple. Most fundamentally, you can send messages and wait for reponses:

```Python
device.send_cmd("echo hello world")

device.wait_for_trace("hello world")

# or combine it together

device.send_cmd_and_wait_for_trace("echo hello world", "hello world")
```

in all '...wait_for_trace()' functions you get a lot of configurability. This configurability on waiting for responses in the way you need really makes the library.

* <strong>resp_req</strong> (optional. default None) - required responses. string or list of strings. all of the provided strings must be seen in stdout in order to be considered successful.
* <strong>resp_avoid</strong> (optional. deafult=None) - avoided responses. string or list of strings. if any of these responses are seen, fail and return immediately.
* <strong>timeout_ms</strong> (optional. deafult=10000)-  max process runtime. 0 == no timeout. if the process does not complete by the given time, fail and return.
* <strong>run_to_completion</strong> (optional. default=False) - run till process completion? Useful if you do not care about the output but you do want the process to run. e.g. "kill 12345"
* <strong>accumulate_traces</strong> (optional. default=False) - should we return everything printed to stdout? by default we only return the last stdout trace we received.
* <strong>cmd_recovery_time_ms</strong> (optional. default=0) - after we complete the desired cmd processing, how long should we wait before tearing down processes and subprocesses. this can be helpful with some larger complexity software services or using hardware programmers that may require some recovery before disconnect for stability purposes.
* <strong>return_on_first_match</strong> (optional. default=False) - return on any found resp\_req instead of waiting for all of resp\_req.
* <strong>quiet</strong> (optional. default=False) - cmd processes stdout is intercepted. should we also print it to our stdout?

<strong>Note:</strong> There are 2 main ways to set the end of the cmd processing, by setting a response(s) that is required or by setting the 'run\_to\_completion' flag to true. Without one of these set, the cmd will likely be issued and return before any data has been processed.

## Return

* was\_successful
  when the start() returns it returns 'wasSuccessful == true' if:
     1) the required parameters, if any, were found.
     2) no avoided responses, if any, were found
     3) we did not timeout before completing processing as directed
* traces - stdout from the cmd
* responses\_remaining - upon returning, what required responses have not yet been found? helpful for troubleshooting failures as well as scenarios where you want to react to a series of async messages but only once.

# Examples

### Example 1: Run process until process completion

Run a process until the process is over

```Python
process_obj = RunProcess(cmd = "echo 'foo'", run_to_completion=True)

wasSuccessful, traces, resp_rem = process_obj.start()

# wasSuccessful is true
```


### Example 2: Run process untill expected responses are seen on stdout

```Python
expected_response = ["bar", "foo"]

wasSuccessfuly, _ = RunProcess(cmd = "echo foo && sleep 1 && echo bar && sleep 100",
                               resp_expected = expected_response).start()

print(f"success: {wasSuccessful}")
```

### Example 3: Run process repeatedly

You can create a process that will be run multiple times

```Python
ip_addr = "127.0.0.1"
expected_response = f"%d bytes from {ip_addr}"

process_obj = RunProcess(cmd = f"ping {ip_addr}",
                         resp_expected = expected_response)

success_count = 0

for int i in range(0,5):

    wasSuccessful, _ = process_obj.start()

    if wasSuccessful:
        success_count += 1

# success_count should be 5
```

### Example 4: Fail on unexpected or "bad" responses

Processes that create bad responses will fail and return immediately

```Python
bad_ip_addr = "1921234.168.1.100"

avoided_responses = ["Unknown host", "Request timeout"]

process_obj = RunProcess(cmd = f"ping {bad_ip_addr} && sleep 100",
                         resp_req = f"%d bytes from {bad_ip_addr}",
                         resp_avoid = avoided_responses)

wasSuccessful, traces, remaining_resp = process_obj.start()

# wasSuccessful should be false immediately (i.e. before sleep 100)
```

### Example 5: Timeout

Processes that run too long will be killed unsuccessfully.

```Python
wasSuccessful, _ = RunProcess( cmd = f"sleep 1000",
                               timeout_ms = 2500).start()

# will return after 2.5 seconds. wasSuccessful should be false
```

### Example 6: Accumulated traces will return everything from stdout

By default, just the last matching trace from stdout will be returned

```Python
wasSuccessful, traces,_ = RunProcess( cmd = f"echo foo && echo bar",
                                      run_to_completion = True,
                                      accumulate_traces=True ).start()

# traces should be 2 lines now:
# foo
# bar
```

### Example 7: Testing script via command line

Instead of calling RunProcess programmatically, you can run it standalone to
test parameters, etc

```Bash
> python ./run_process -c "echo foo && echo bar && echo baz" -r foo,baz
```

For run with -h for help text

```Bash
> python ./run_process -h
```

# SUPPORT

For bugs: Report reproduction steps and OS to bugs@rmlconsulting.dev - if you
know how to fix it, please just push a PR

For questions and customization requests: questions@rmlconsulting.dev
