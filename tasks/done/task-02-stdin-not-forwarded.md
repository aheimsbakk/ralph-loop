# task-02-stdin-not-forwarded

## Severity
High

## Rule
III.9 (Strict Boundaries & SRP)

## Summary
Implement explicit stdin forwarding to the wrapped command.

## Problem
The blueprint and README state "ralph-loop passes stdin through to the wrapped
command." However, `subprocess.Popen(..., stdin=None, ...)` leaves stdin as the
default inherit behavior. This works for interactive terminals but breaks when
stdin is a pipe — the child process does not receive piped data because the PTY
pair replaces stdout/stderr channels, and stdin is not explicitly managed.

## Evidence
`runtime.py`: `stdin=None` in `subprocess.Popen()` call.

## Fix
1. Set `stdin=subprocess.PIPE` in `subprocess.Popen()`.
2. Spawn a background thread that reads from `sys.stdin` and writes to
   `process.stdin`.
3. Close `process.stdin` when stdin reaches EOF.
4. Handle the case where stdin is a terminal (interactive) — skip pipe mode.

## Files
- `src/ralph_loop/runtime.py`

## Tests
- Add test: `test_loop_supervisor_forwards_piped_stdin`
- Add test: `test_loop_supervisor_stdin_eof_stops_writer`
- Add test: `test_loop_supervisor_no_stdin_pipe_when_terminal`
