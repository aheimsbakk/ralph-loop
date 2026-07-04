# task-12-inefficient-promise-regex

## Severity
Low

## Rule
— (Performance)

## Summary
Optimize `PROMISE_PATTERN` regex for better performance.

## Problem
`PROMISE_PATTERN` uses `r"<promise>([\s\S]*?)</promise>"` which matches
across newlines via `[\s\S]`. This is slower than using `re.DOTALL` with
`(.*?)`. The `fullmatch` call is correct, but the regex engine performs
more backtracking with `[\s\S]` than with `DOTALL`.

## Evidence
`runtime.py`: `PROMISE_PATTERN = re.compile(r"<promise>([\s\S]*?)</promise>")`

## Fix
1. Replace with `re.compile(r"<promise>(.*?)</promise>", re.DOTALL)`.
2. Verify all existing tests pass (behavior is identical).

## Files
- `src/ralph_loop/runtime.py`

## Tests
- All existing promise-related tests in `test_runtime.py` must pass:
  `test_promise_detected_normalizes_whitespace`
  `test_promise_detected_handles_missing_expected_value`
  `test_promise_detected_ignores_non_final_promise_line`
  `test_promise_detected_accepts_final_non_empty_promise_line`
  `test_promise_detected_ignores_terminal_control_sequences`
