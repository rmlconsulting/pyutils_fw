################################################################################
# BSD 2-Clause License
#
# Copyright (c) 2025, RML Consulting, LLC
# info@rmlconsulting.dev
# https://github.com/rmlconsulting/pyutils-fw
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
################################################################################
""" Module providing ability to run a process and grab relevant output """

import logging
import multiprocessing
import subprocess
import re
import time
import signal
import psutil

# Create a logging object with a null handler. if the caller of this class
# does not configure a logger context then no messages will be printed.
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

class RunProcess():
    """ Run Process class. Groups functionality around thread management,
        regex processing, etc to make interacting with systems processes easier
        """

    def __init__(self,
                 cmd, # command to run
                 resp_req = None, # required responses. string or list of strings
                 resp_avoid = None, # avoided responses. string or list of strings
                 timeout_ms = 10000, # max process runtime. 0 == forever
                 run_to_completion = False, # run till process completion?
                 accumulate_traces = False, # should we return all stddout?
                 # for stability: time to wait after cmd completion before
                 # killing the process. helpful when interacting with
                 # systems or hardware that need recovery
                 cmd_recovery_time_ms = 0,
                 return_on_first_match = False, # return on any found resp_req
                 quiet = False,
                 ):

        ######################################
        # core vars
        ######################################

        self.cmd = cmd # command to run
        self.resp_req = resp_req # responses required

        # responses to avoid - trigger immediate failure
        self.resp_avoid = resp_avoid

        # max duration of the process before it is shutdown
        self.timeout_ms = timeout_ms

        # run the process to completion
        self.run_to_completion = run_to_completion

        # accumulate all stdout to return
        self.accumulate_traces = accumulate_traces

        # return immediately if we found any required response, regardless
        # of the number of required responses
        self.return_on_first_match = return_on_first_match

        self.cmd_recovery_time_ms = int(cmd_recovery_time_ms)

        # should we allow cmd's stdout to go to stdout?
        self.quiet = quiet

        ######################################
        # Var Cleanup - working with a list simplifies logic below
        ######################################
        if self.resp_req and not isinstance(self.resp_req, list):
            self.resp_req = [self.resp_req]

        if self.resp_avoid and not isinstance(self.resp_avoid, list):
            self.resp_avoid = [self.resp_avoid]

        ######################################
        # internal working vars
        ######################################

        # create a thread safe value for pass PID of the subprocess back to
        # the main thread. this is a ctypes value type of 'i' or integer
        self.__subprocess_pid = multiprocessing.Value('i', 0, lock=True)
        # thread safe queue for passing stdout back to the main process
        self.__msg_queue = multiprocessing.Queue()

        # created the process obj but don't start. this is reusable across
        # multiple run_process start() calls.
        self.__process = multiprocessing.Process(target = self._run_process,
                                                 args   = (cmd,
                                                           self.__msg_queue,
                                                           self.__subprocess_pid
                                                          ),
                                                 daemon = True)

    def __kill_child_processes(self, parent_pid, sig=signal.SIGTERM):
        """ send the sigterm to the parent_pid and all subprocesses """
        try:
            parent = psutil.Process(parent_pid)
        except psutil.NoSuchProcess:
            return

        children = parent.children(recursive=True)

        for process in children:
            process.send_signal(sig)

    def stop(self):
        """ stop the running process provided by the 'cmd' var """
        if self.__process and self.__process.is_alive():
            self.__kill_child_processes( self.__subprocess_pid.value )

    def is_running(self):
        """ is the 'cmd' process running """
        return self.__process.is_alive()

    def _run_process(self, cmd, msg_queue, pid_value):
        """ function that acutally runs the process.
            cmd - cmd to run
            msg_queue - passes stdout back to the parent process
            pid_value - multiprocessing value to pass subprocess pid back to the
                        parent process
        """

        p = subprocess.Popen( cmd,
                              shell=True,
                              encoding="ISO-8859-1",
                              stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT)

        # update the value of the PID from the subprocess that was generated
        # this var type needs to be Value() to be managed correctly from a
        # multiprocessing library perspective
        pid_value.value = p.pid

        # put anything on stdout into the thread-safe queue
        # readline will end iter processing when the subprocess completes
        # there's no way to make this process non blocking so we cant
        # have this function kill the subprocess in case of timeout. that
        # will have to be maintained by the top level
        for stdout_line in iter(p.stdout.readline, ""):
            if msg_queue:
                msg_queue.put( stdout_line )

        p.stdout.close()
        return_code = p.wait()
        if return_code:
            raise subprocess.CalledProcessError(return_code, cmd)

    def start(self):
        """ start the process that will execute 'cmd' """

        # don't allow a 2nd start of this object
        if (self.__process is not None and self.__process.is_alive()):
            raise Exception("Process already running")

        # set success to None until we know we're successful or not
        success = None
        traces_to_return = ""
        stop_processing = False

        # make a local copy of our class variables we'll edit in this func
        # this will allow us to run a run_process object multiple tiems without
        # reinstantiation
        resp_req = None
        if self.resp_req:
            resp_req = self.resp_req.copy()

        self.__process.start()

        now = lambda: int(round(time.time() * 1000))

        start_time = now()

        try:

            while True:

                # check for timeout
                if (self.timeout_ms != 0 and (now() - start_time > self.timeout_ms)):
                    success = False
                    break

                if self.__msg_queue.empty():
                    # if the process is dead then we don't need to wait anymore
                    if not self.__process.is_alive():
                        break
                    else:
                        # if we have no data sleep for a bit to not chew up the processor
                        time.sleep(0.001)
                else:
                    line = self.__msg_queue.get_nowait().strip()

                    if self.accumulate_traces:
                        traces_to_return += line + "\n"
                    else:
                        traces_to_return = line + "\n"

                    # print this to stdout
                    if not self.quiet:
                        print(line)

                    # look through teh list of required responses. if we dont have
                    # any then just return
                    if (resp_req and len(resp_req)):

                        # if we found a required response, remove it from the list
                        for resp in resp_req:
                            # if this line matches one from the list then remove it
                            if re.search(resp, line, re.IGNORECASE):
                                resp_req.remove(resp)

                                if (self.return_on_first_match):
                                    success = True
                                    # no need to look at any more data
                                    stop_processing = True
                                    break

                                # if we have no more responses we're looking for, just
                                # return
                                if (len(resp_req) == 0 and not self.run_to_completion):
                                    # sleep some, if we kill the process immediately, sometimes
                                    # the underlying processes can hang
                                    if (self.cmd_recovery_time_ms > 0):
                                        time.sleep( self.cmd_recovery_time_ms / 1000 )

                                    # no need to look at any more data
                                    stop_processing = True

                                    success = True
                                    break

                                # get more data so we can keep processing
                                continue

                    # we found everything we're looking for and are not letting
                    # the process self terminate
                    elif not self.run_to_completion:
                        success = True
                        # no need to look at any more data
                        stop_processing = True
                        break

                    if (self.resp_avoid and len(self.resp_avoid)):
                        # if we found a required response, remove it from the list
                        for resp in self.resp_avoid:
                            # if this line matches one from the list then remove it
                            if re.search(resp, line, re.IGNORECASE):
                                logger.debug("YIKES: found response to avoid [" + line + "]")
                                success = False
                                # no need to look at any more data
                                stop_processing = True
                                break

                    if stop_processing:
                        break

        finally:

            # kill any spawned processes associated with the process
            if self.__subprocess_pid.value:
                self.__kill_child_processes(self.__subprocess_pid.value)

            # if the process is still alive then kill it
            if self.__process.is_alive():
                #print("joining...:" + str(self.__subprocess_pid.value))
                self.__process.terminate()
                self.__process.join()

        if success is None:
            success = False

        return (success, traces_to_return.strip(), resp_req)

################################################################################
# CLI PROCESSING FUNCTIONS
# ------------------------------------------------------------------------------
# things below here are so you can use this as a stand-alone script on the CLI
################################################################################

def csv_to_list(csv_str):
    return [item.strip() for item in csv_str.split(',')]

def process_cli_args():
    """ process command line args """
    parser = argparse.ArgumentParser(description="A tool to Run a CLI process and handle its output")

    parser.add_argument('--cmd',
                        '-c',
                        help = "command to run",
                        type=str,
                        required=True)

    parser.add_argument('--avoided_resp',
                        '-a',
                        help = "Quit immediately if you see this regexp response",
                        type=csv_to_list,
                        required=False)

    parser.add_argument('--required_resp',
                        '-r',
                        help = "comma separated list of regexp required responses",
                        type=csv_to_list,
                        required=False)

    parser.add_argument('--accumulate_traces',
                        '-n',
                        help = "comma separated list of required responses",
                        action='store_true',
                        default=False)

    parser.add_argument('--process_recovery_time_ms',
                        '-p',
                        help = "how long to wait after completion before we return. for stability of complex process called repeatedly.",
                        type=int,
                        required=False,
                        default=0)

    parser.add_argument('--return_on_first_match',
                        '-i',
                        help = "return immediately upon finding any required_resp",
                        action='store_true',
                        default=False)

    parser.add_argument('--run_to_completion',
                        '-x',
                        help = "run until the process closes naturally",
                        action='store_true',
                        default=False)

    parser.add_argument('--timeout_ms',
                        '-t',
                        help = "timeout_ms",
                        type=int,
                        required=False,
                        default=10000)

    parser.add_argument('--quiet',
                        '-q',
                        help = "should 'cmd' process stdout be printed to stdout?",
                        action='store_true',
                        default=False)

    args = parser.parse_args()

    return args

def main():
    """ main """

    args = process_cli_args()

    if not args.quiet:
        print("########## Beginning Process ##########")

    p = RunProcess( cmd = args.cmd,
                    resp_req = args.required_resp,
                    resp_avoid = args.avoided_resp,
                    timeout_ms = args.timeout_ms,
                    run_to_completion = args.run_to_completion,
                    accumulate_traces = args.accumulate_traces,
                    cmd_recovery_time_ms = args.process_recovery_time_ms,
                    return_on_first_match = args.return_on_first_match,
                    quiet = args.quiet,
                    )

    success, traces, responses_remaining = p.start()

    if not args.quiet:
        print("########## End of Process ##########")

    print(f" success = {success}")
    print(f" traces = '{traces}'")
    print(f" resp_req_remaining = {responses_remaining}")

if __name__ == '__main__':
    import argparse
    main()
