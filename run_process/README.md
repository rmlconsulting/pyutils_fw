# RunProcess

Run process allows you to interact with system processes and react to the
response in real-time. This will also manage any child/subprocesses the command
you call may have spawned.

This has been tested on Mac, Linux and Windows.

For bugs: Report reproduction steps and OS to bugs@rmlconsulting.dev
For questions and customization requests: questions@rmlconsulting.dev

You can create a process to run by instantiating RunProcess like:

> process_obj = RunProcess("echo foo")

Then, you can start the process via:

> wasSuccessful, traces, responses_remaining = process_obj.start()

### Example 1: Run process until process completion

Run a process until the process is over

>
> process_obj = RunProcess(cmd = "echo 'foo'", run_to_completion=True)
>
> wasSuccessful, traces, resp_rem = process_obj.start()
>

### Example 2: Run process untill expected responses are seen on stdout

>
> expected_response = ["bar", "foo"]
>
> wasSuccessfuly, _ = RunProcess(cmd = "echo foo && sleep 1 && echo bar && sleep 100",
>                          resp_expected = expected_response).start()
>
> print(f"success: {wasSuccessful}")
>

### Example 3: Run process repeatedly

You can create a process that will be run multiple times

>
> ip_addr = "127.0.0.1"
> expected_response = f"%d bytes from {ip_addr}"
>
> process_obj = RunProcess(cmd = f"ping {ip_addr}",
>                          resp_expected = expected_response)
>
> success_count = 0
>
> for int i in range(0,5):
>
>     wasSuccessful, _ = process_obj.start()
>
>     if wasSuccessful:
>         success_count += 1
>
> // success_count should be 5
>

### Example 4: Fail on unexpected or "bad" responses

Processes that create bad responses will fail and return immediately

>
> bad_ip_addr = "1921234.168.1.100"
> expected_response = f"%d bytes from {bad_ip_addr}"
>
> avoided_responses = ["Unknown host", "Request timeout"]
>
> process_obj = RunProcess(cmd = f"ping {bad_ip_addr} && sleep 100",
>                          resp_req = expected_response,
>                          resp_avoid = "Request timeout")
>
>
> wasSuccessful, traces, remaining_resp = process_obj.start()
>
> // wasSuccessful should be false immediately (i.e. before sleep 100)
>

### Example 5: Timeout

Processes that run too long will be killed unsuccessfully.

>
> (wasSuccessful, \_) = RunProcess( cmd = f"sleep 1000",
>                           timeout_ms = 2500).start()
>
> // will return after 2.5 seconds. wasSuccessful should be false
>

### Example 6: Accumulated traces will return everything from stdout

By default, just the last matching trace from stdout will be returned

>
> (\_, traces) = RunProcess( cmd = f"echo foo && echo bar",
>                                       run_to_completion = True ).start()
>
> //traces should be 2 lines:
> //foo
> //bar
>

### Example 6: Testing script via command line

Instead of calling RunProcess programmatically, you can run it standalone to
test

>
> \> python ./run_process
>
>

