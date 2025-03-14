################################################################################
#
# BSD 2-Clause License
#
# Copyright (c) 2025, RML Consulting, LLC
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

import pytest
import datetime
import sys
import os
import re
import logging

# Create a logging object with a null handler. if the caller of this class
# does not configure a logger context then no messages will be printed.
logger = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

class StdoutCapture():

    # precompiled regex to remove ansi escape chars
    ansi_escape = re.compile(r'(\x9B|\x1B\[)[0-?]*[ -\/]*[@-~]')

    def __init__(self, logging_dir, logging_name = "log", \
            logging_struct = None):

        # mark that we're initializing. we set it to complete at the bottom
        # of this function. otherwise any print statements that get sent
        # to this class in the meantime will throw warnings
        self.init_complete = False

        # declare outfile to None in the event we want to log something
        # before the end of this init func
        self.outfile = None

        # store stdout
        self.orig_stdout = sys.stdout

        # redirect stdout to this class
        sys.stdout = self

        if (not logging_struct):
            logging_struct = "logs/{date:%Y%m}/{date:%Y%m%d}/{date:%Y%m%dT%H%M%S}"

        # within the logging directory, figure out the subdirectory
        logging_subdirs = self._get_logging_subdir_structure(logging_struct)

        # store the absolute path of the logging subdir for this test run
        self._logging_dir = os.path.abspath(logging_dir + "/" + logging_subdirs)

        # make sure logging dir exists
        if (False == os.path.isdir(self._logging_dir)):
            os.makedirs(self._logging_dir)

        logfile = self._get_path_for_new_file(logging_name)

        self.outfile = open(logfile, "w+")

        self.init_complete = True

    def __del__(self):
        sys.stdout = self.orig_stdout

    def _get_logging_subdir_structure(self, logging_struct):

        """
            given a pattern string, replace all patterns '{pattern}' with
            the appropriate value and return the final string
        """

        if (logging_struct is None):
            raise Exception("illegal value for logging structure: " + str(logging_struct))

        currtime = datetime.datetime.now()

        # start off with the string with patterns. we're going to
        # replace one pattern at a time
        log_subdir = logging_struct

        # we're going to run this search in a couple places so go ahead and
        # precompile this pattern
        pattern_search = re.compile("^(.*?)\{([^}]+)\}(.*)$")

        # search the logging struct string for a pattern
        logging_struct_match = pattern_search.match(log_subdir)

        # keep processing the string until there are no more "{}" patterns defined
        while(logging_struct_match is not None):
            #print("matches: " + str(logging_struct_match.groups()))
            # stuff before the pattern
            preamble = logging_struct_match.group(1)
            pattern = logging_struct_match.group(2)
            # stuff after the pattern
            tail = logging_struct_match.group(3)

            pattern_replacement = ""

            # replace the pattern with the appropriate value
            if (pattern.startswith("date:")):
                pattern_replacement = currtime.strftime(pattern[5:])
            else:
                raise Exception("unknown logging_structure pattern [" + str(pattern) + "]")

            # rebuild the string, with the pattern replaced now
            log_subdir = preamble + pattern_replacement + tail

            # look for the next pattern
            logging_struct_match = pattern_search.match(log_subdir)


        #print("log_subdir: " + log_subdir)
        return log_subdir

    def _get_path_for_new_file(self, filename):

        curr_time = date = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

        #prepend the timestamp to the filename
        new_filename = f"{curr_time}_{filename}.log"

        return os.path.join(self._logging_dir, new_filename)

    def _escape_ansi(self, line):
        return self.ansi_escape.sub('', line)

    def write(self, string):
        # print to stdout
        self.orig_stdout.write(string)

        # log the string to file
        if (self.outfile and not self.outfile.closed):
            # remove all the non-ascii chars
            string = string.encode("ascii",errors="ignore").decode()
            # get rid of junk at the beginning, end and Carraige returns in the middle
            string = string.rstrip().lstrip().replace("\r",'')
            # get rid of the color info from the string
            string = self._escape_ansi(string)
            self.outfile.write(string + "\n")

        # if we have completed initialization, we should have an outfile defined
        elif self.init_complete:
            self.orig_stdout.write("something is wrong")

    def isatty(self):
        return True

    def flush(self):
        self.orig_stdout.flush()
        if (self.outfile and not self.outfile.closed):
            self.outfile.flush()

    def log_to_new_file(self, fname, message=None):
        self.outfile.close()
        new_file = self._get_path_for_new_file(fname)
        self.outfile = open(new_file, "w+")

        if message:
            for line in message:
                self.outfile.write(line)

