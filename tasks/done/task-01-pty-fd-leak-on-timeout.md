# task-01-pty-fd-leak-on-timeout

## Severity
High

## Rule
III.13 (Resource Cleanup)

## Summary
Close slave PTY fd before process termination to prevent silent hangs.

## Problem
In `runtime.py`, `run_iteration()` opens a PTY pair (`master_fd`, `slave_fd`).
The slave fd is passed to `subprocess.Popen` as stdout/stderr. On the timeout
path, `_stop_current_process` waits for the process to terminate, but the slave
fd is never explicitly closed before `process.terminate()`. The child process
keeps the fd open in its descriptor table, so `terminate()` (SIGTERM) may not
cause the process to exit, and the loop blocks indefinitely.

## Evidence
`runtime.py` line: `stdout=slave_fd, stderr=slave_fd`
No `os.close(slave_fd)` call before or during termination.

## Fix
1. Close `slave_fd` immediately after `subprocess.Popen()` returns (the child
   already has a copy via the fd redirection).
2. Add `os.close(slave_fd)` in `_stop_current_process` before
   `process.terminate()` as a safety net.
3. Ensure `finally` block closes `master_fd` only (slave is already closed).

## Files
- `src/ralph_loop/runtime.py`

## Tests
- Add test: `test_loop_supervisor_timeout_closes_slave_fd`
- Verify `_stop_current_process` does not hang when process ignores SIGTERM.
