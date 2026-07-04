# task-05-unbounded-output-buffer

## Severity
Medium

## Rule
III.14 (Bounded Caches & Memory)

## Summary
Enforce a maximum output buffer size to prevent unbounded memory growth.

## Problem
`output_parts: list[str]` in `LoopSupervisor.run_iteration()` grows without
limit for every iteration. For long-running sessions with many iterations or
verbose child processes, this can consume significant memory. The blueprint
specifies "Captured output buffers" but does not define a size limit.

## Evidence
`runtime.py`: `output_parts: list[str] = []` with continuous `append` calls.

## Fix
1. Define a constant `MAX_OUTPUT_BYTES = 1024 * 1024` (1 MB) in `constants.py`.
2. After each iteration, truncate `output_parts` to the last N elements that
   fit within the byte limit.
3. Alternatively, cap the total list size and discard oldest entries.
4. Document the limit in the blueprint.

## Files
- `src/ralph_loop/constants.py`
- `src/ralph_loop/runtime.py`
- `BLUEPRINT.md`

## Tests
- Add test: `test_output_buffer_truncated_at_max_bytes`
- Add test: `test_promise_detected_after_truncation_still_works`
