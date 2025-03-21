# pyutils_fw
FW-centric python utilities

### RunProcess
A utility for intelligently pulling any cli tool into python land. This utility will spin up a new thread and allow you to optionally monitor desired and undesired responses with lots of optionality for timeouts and data processing and will also handle thread and subprocess cleanup.

### Device Comms
Make it easy to interact with devices over serial / JTag (SWD) / Websockets. This takes the pain out of thread management, string parsing, managing timeouts and multiple devices, etc etc. Allows you to send commands and monitor logs of a device intelligently.

### stdout_logger
Easily capture everything you print() to stdout. The logger allows you to specify a directory structure as well as create new logfiles per test/action/etc without too much effort.
