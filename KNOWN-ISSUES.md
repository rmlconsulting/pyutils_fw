# Known issues (0.1.0)

Defects that are known, deliberately NOT fixed in the 0.1.0 packaging pass,
and recorded here so nobody rediscovers them the hard way. The 0.1.0 rule
was: repair the modules autoHILT imports (`pyutils_fw.relays.NumatoDevice`,
`pyutils_fw.device_comms.SerialCommsDevice`, `pyutils_fw.device_comms
.JLinkDevice`'s import path), package everything, and leave the rest as-is
but documented.

## device_comms/jlink_device.py

Importable everywhere (so the `pyutils_fw.device_comms` re-exports work on
any OS), but **running it is POSIX-only today**, and it has known defects.
Repairs are slated to land alongside autoHILT's M3 hardware milestone,
which is the first thing that exercises it end to end.

- Spawns `JLinkExe`/`JLinkRTTClient` through `/bin/sh -c` - no Windows.
- Uses `select.select()` on subprocess pipes, which only works on sockets
  on Windows.
- Bring-up succeeds only on `"Cortex-M4 identified"` - hardcoded; any other
  core times out the startup loop even when the connection is fine.
- No flash/program capability; this class only does RTT logging and J-Link
  commander passthrough.
- RTT telnet ports are handed out from a class-level counter
  (`last_telnet_port_used`), so ports are never reused within a process and
  two processes can collide.
- `__start_logging_process` returns `false` (NameError) on the
  stop-requested path while draining the SEGGER header.

## relays/lcus_relay_board.py

**Deprecated, non-functional. Do not use.** Kept only as a protocol
reference for the LCUS command format.

- Does not inherit `RelayBase` but calls
  `super().__init__(num_relays=...)` - `object.__init__` raises TypeError,
  so construction has never worked in this form.
- `_deactiate_relay` is misspelled, so even with a base class it would
  never be dispatched.
- `self.relay_status = [ channel ] = is_active` is a chained assignment
  that raises at runtime.
- `status_inquiry` passes an int (`0xFF`) to `serial.write()`, which
  requires bytes.

## tee/

- Instantiating `Tee` rebinds `sys.stdout` **and** `sys.stderr`
  process-wide as a constructor side effect, and restores them in
  `__del__` - destructor-timing dependent.
- The saved "original stderr" is actually stdout
  (`self.orig_stderr = sys.stdout`), so after cleanup, stderr points at
  the original stdout.

## encrypt/

- Imports `pyAesCrypt`, which is **not** a declared dependency (that's why
  `pyutils_fw.encrypt` deliberately re-exports nothing). Install
  pyAesCrypt yourself before using `pyutils_fw.encrypt.AESEncrypt`.
- Error paths do `raise("message string")`, which raises TypeError instead
  of the intended exception.

## run_process/

- A `RunProcess` object is not restartable: the `multiprocessing.Process`
  is created once in `__init__`, so a second `start()` after completion
  raises. Build a new object per run.
- The child's exit code is checked inside the child process
  (`CalledProcessError` raised there), so the parent never sees it;
  `start()`'s success verdict is based solely on response matching and
  timeouts.

## event_generator/

- `EventCoordinator.stop()` dereferences `self._timer` without a None
  check, so calling `stop()` before `start()` (or twice) raises
  AttributeError.
