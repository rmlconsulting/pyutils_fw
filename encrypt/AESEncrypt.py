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

import logging
import os
import pyAesCrypt
import io

# Create a logging object with a null handler. if the caller of this class
# does not configure a logger context then no messages will be printed.
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


class AESEncrypt():

    def __init__(self, pw):

        # save the password
        self.__pw = pw

    def encrypt_file(self, source_file, encrypted_output_file):

        # make sure source file exists
        source_file = os.path.abspath(source_file)
        if not os.path.exists(source_file):
            raise("Could not encrypt. file does not exist: " + str(source_file))

        pyAesCrypt.encryptFile( source_file, encrypted_output_file, self.__pw)

    def decrypt_file(self, encrypted_source_file, output_file):

        # make sure encrypted source file exists
        encrypted_source_file = os.path.abspath(encrypted_source_file)
        if not os.path.exists(encrypted_source_file):
            raise("Could not decrypt. file does not exist: " + encrypted_source_file)

        pyAesCrypt.decryptFile( encrypted_source_file, output_file, self.__pw)

    def decrypt_var_to_file(self, encrypted_var, output_file):

        # 64k buffer size - this is mandatory for working with byte streams
        bufferSize = 64 * 1024

        # turn the encrypted data into a byte stream
        input_data = io.BytesIO( encrypted_var )

        # initialize the decrypted bytestream
        decrypted_data = io.BytesIO()

        pyAesCrypt.decryptStream( input_data,
                                  decrypted_data,
                                  self.__pw,
                                  bufferSize,
                                  len(encrypted_var))

        # write the decrypted byte stream to disk
        with open(output_file, 'wb') as f_out:
            f_out.write( decrypted_data.getbuffer() )

################################################################################
# CLI PROCESSING FUNCTIONS
# ------------------------------------------------------------------------------
# things below here are so you can use this as a stand-alone script on the CLI
################################################################################

def process_cli_args():
    parser = argparse.ArgumentParser(description="A tool to encrypt/decrypt files from the CLI")

    parser.add_argument('--input_file',
                        '-i',
                        help = "the input/starting file",
                        type=str,
                        required=True)

    parser.add_argument('--output_file',
                        '-o',
                        help = "where to put the processed file",
                        type=str,
                        required=True)

    parser.add_argument('--pw',
                        '-p',
                        help = "password to use for encrypt/decrypt",
                        type=str,
                        required=True)

    parser.add_argument('--action',
                        '-a',
                        help = "action to take on the input file",
                        choices = ["encrypt", "decrypt"],
                        type=str,
                        required=True)

    args = parser.parse_args()

    return args

def main():

    args = process_cli_args()

    contents = ""

    enc_obj = AESEncrypt(args.pw)

    if (args.action == "encrypt"):
        print("encrypting ...[" + args.input_file + "]")
        enc_obj.encrypt_file( source_file = args.input_file,
                              encrypted_output_file = args.output_file)

    elif (args.action == "decrypt"):
        print("decrypting...[" + args.input_file + "]")
        enc_obj.decrypt_file( encrypted_source_file = args.input_file,
                              output_file = args.output_file)
    else:
        raise("Unknown action: " + str(args.action))

    print("done")

if __name__ == '__main__':
    import argparse
    main()
