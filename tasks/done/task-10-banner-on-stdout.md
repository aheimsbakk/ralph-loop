# task-10-banner-on-stdout

## Severity
Low

## Rule
III.9 (Strict Boundaries & SRP)

## Summary
Print the start banner to stderr instead of stdout.

## Problem
`_print_start_banner` in `commands.py` prints to `sys.stdout`, which mixes
with the child process output streamed to stdout. Users piping ralph-loop
output to a file or another command will capture the banner lines, polluting
the data stream.

## Evidence
`commands.py`: `print("ralph-loop started.")` and subsequent banner lines use
default `sys.stdout`.

## Fix
1. Change all `print()` calls in `_print_start_banner` to use
   `file=sys.stderr`.
2. Update tests in `test_commands.py` that assert banner content in
   `capsys.readouterr().out` to check `.err` instead.

## Files
- `src/ralph_loop/commands.py`
- `tests/test_commands.py`

## Tests
- Verify banner appears in stderr, not stdout, when running with piped output.
