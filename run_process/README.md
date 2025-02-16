# RunProcess

RunProcess allows you to interact with system processes and react to the response in real-time.

You can create a process to run by instantiating RunProcess like:

```Python
process_obj = RunProcess("echo foo")
```

Then, you can start the process via:

```Python
wasSuccessful, traces, responses_remaining = process_obj.start()
```

This has been tested on Mac, Linux and Windows.

This will also manage any child/subprocesses the command you call may have spawned.

## Parameters

just running a cli command can be achieved with os.system(...), what make this
class more functional is the customization around how to handle the data
coming back from the processes stdout, when and how to return, ability to handle
timeouts and the cleanup of subprocesses that the command may have spawned

* <strong>cmd</strong> - cli command to run
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
