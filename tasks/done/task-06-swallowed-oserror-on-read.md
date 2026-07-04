# task-06-swallowed-oserror-on-read

## Severity
Medium

## Rule
III.11 (Error Handling)

## Summary
Distinguish expected fd closure from unexpected errors in `_read_available_output`.

## Problem
`_read_available_output` catches `OSError` with `EBADF`/`EIO` and returns
`False`, silently breaking the read loop. This is correct when the fd was
intentionally closed, but if `EBADF` occurs because the fd was closed elsewhere
(e.g., a race between the signal handler and the read loop), the break is
silent and the caller has no way to distinguish expected from unexpected
closure.

## Evidence
`runtime.py`: `except OSError as error: if error.errno in {errno.EBADF, errno.EIO}: return False`

## Fix
1. Add a parameter or check to determine if the fd closure was expected
   (e.g., `self.current_output_fd` matches the fd being read).
2. If the fd was closed unexpectedly (process still alive), log a warning and
   continue reading from any remaining output, or re-raise if no recovery is
   possible.
3. If the fd was closed intentionally (process exited, fd already closed),
   return `False` as before.

## Files
- `src/ralph_loop/runtime.py`

## Tests
- Add test: `test_read_unexpected_ebadf_warns`
- Add test: `test_read_expected_ebadf_returns_false`
