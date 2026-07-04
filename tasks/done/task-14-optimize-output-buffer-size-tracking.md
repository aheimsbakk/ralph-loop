---
id: task-14-optimize-output-buffer-size-tracking
priority: low
status: pending
description: |
  Optimize the output buffer size tracking to avoid $O(N)$ recalculations in `runtime.py`.
  
  Plan:
  1. Modify `OutputReader` to maintain a running `current_size` attribute.
  2. Update `LoopSupervisor` to use this size for truncation checks.
  3. Remove the manual byte-counting loop in `_truncate_output_parts`.
  4. Run tests.
---
