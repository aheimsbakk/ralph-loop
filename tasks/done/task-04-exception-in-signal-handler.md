# task-04-exception-in-signal-handler

## Severity
Medium

## Rule
III.11 (Error Handling)

## Summary
Replace exception-raising signal handler with a thread-safe flag pattern.

## Problem
`_handle_signal` raises `LoopInterrupted` directly from within a signal handler.
CPython does not guarantee that raising exceptions from signal handlers is safe —
the interpreter may be in an inconsistent state (e.g., holding a GIL lock, in
the middle of a C extension call). While this works in practice on CPython, it
is not portable and can cause crashes on alternative implementations.

## Evidence
`runtime.py`: `def _handle_signal(self, signum, _frame)` raises `LoopInterrupted(signum)`.

## Fix
1. Replace the exception with a `threading.Event` flag set by the signal handler.
2. In `_handle_signal`, set the event and then terminate the current process.
3. In `run_iteration`, check the event after each iteration and after each
   `select.select()` call. If set, raise `LoopInterrupted` in the main thread.
4. This keeps exception raising in the main thread where it is safe.

## Files
- `src/ralph_loop/runtime.py`

## Tests
- Add test: `test_signal_handler_sets_event_not_raises`
- Add test: `test_loop_interrupted_raised_in_main_thread`
