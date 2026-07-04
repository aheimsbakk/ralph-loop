# task-03-silent-hang-on-pipe-input

## Severity
High

## Rule
III.12 (Network & Async Resilience)

## Summary
Add a global session timeout or document the hang condition when child waits for stdin.

## Problem
When stdin is piped and the child process blocks waiting for input that
ralph-loop never forwards (see task-02), the child hangs indefinitely. The
current per-iteration timeout (`--timeout`) does not cover this case because the
child is still running — it is blocked on stdin, not stuck in computation.
There is no global timeout mechanism.

## Evidence
README documents: "Piped input is not replayed between iterations."
But no warning about the child blocking on stdin.

## Fix
1. Add a new `--session-timeout` option (positive integer, seconds) that
   applies to the entire ralph-loop session, not just individual iterations.
2. Implement a timer thread or monotonic check in the main loop that terminates
   the session when the global timeout is reached.
3. Return a distinct exit code (e.g., 125) for session timeout.
4. Update README and help text to document the hang condition.

## Files
- `src/ralph_loop/cli.py`
- `src/ralph_loop/commands.py`
- `src/ralph_loop/models.py`
- `README.md`

## Tests
- Add test: `test_run_command_session_timeout_terminates_loop`
- Add test: `test_session_timeout_exit_code_is_125`
