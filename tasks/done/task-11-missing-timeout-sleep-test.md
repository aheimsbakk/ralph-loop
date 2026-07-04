# task-11-missing-timeout-sleep-test

## Severity
Low

## Rule
IV.19 (Test-Driven Fixes)

## Summary
Add test verifying sleep is not called after a timeout iteration.

## Problem
The test suite does not verify that `time.sleep` is not called after a
timeout iteration (exit code 124). The current behavior returns immediately
on timeout, which is correct, but there is no test asserting this interaction.

## Evidence
`tests/test_commands.py`: `test_run_command_reports_timeout` mocks a timeout
result but does not check whether `sleep` was called.

## Fix
1. In `test_run_command_reports_timeout`, mock `time.sleep` and collect calls.
2. Assert `sleep` was not called after the timeout iteration.

## Files
- `tests/test_commands.py`

## Tests
- `test_run_command_reports_timeout` should include:
  `assert sleeps == []`
