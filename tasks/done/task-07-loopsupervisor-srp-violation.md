# task-07-loopsupervisor-srp-violation

## Severity
Medium

## Rule
III.9 (Strict Boundaries & SRP)

## Summary
Split `LoopSupervisor` into smaller focused classes.

## Problem
`runtime.py` — `LoopSupervisor` is 237 lines and handles five responsibilities:
subprocess creation and PTY setup, PTY output reading and streaming, signal
installation and restoration, termination grace logic, and output finalization.
This violates the Single Responsibility Principle.

## Evidence
`runtime.py`: `LoopSupervisor` class contains `install_signal_handlers`,
`run_iteration`, `_handle_signal`, `_stop_current_process`,
`_read_available_output`, `_finalize_output`, `_close_fd`.

## Fix
Extract the following classes:
1. `ProcessRunner` — `subprocess.Popen` creation, PTY fd management,
   process lifecycle (`terminate`, `kill`, `poll`).
2. `OutputStreamer` — reads from PTY master fd, decodes UTF-8, prints to
   terminal, appends to output buffer.
3. `SignalHandler` — installs and restores signal handlers, manages the
   interruption event flag.
4. `LoopSupervisor` — orchestrates the above three classes in the main loop.

## Files
- `src/ralph_loop/runtime.py` (split into multiple files or kept as internal
  module classes)

## Tests
- Existing tests in `test_runtime.py` must continue to pass.
- Add unit tests for each extracted class.
