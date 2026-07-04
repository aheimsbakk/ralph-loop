---
id: task-13-split-runtime-utils
priority: medium
status: pending
description: |
  Split `src/ralph_loop/runtime.py` to comply with Rule 17 (Modular File Structure).
  The file exceeds 200 lines.
  
  Plan:
  1. Create `src/ralph_loop/utils.py`.
  2. Move `normalize_whitespace`, `strip_terminal_control_sequences`, and `promise_detected` to `utils.py`.
  3. Move `ensure_command_available` and `signal_exit_code` to `utils.py`.
  4. Update imports in `runtime.py`, `commands.py`, and `cli.py`.
  5. Run tests.
---
