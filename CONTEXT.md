# Project context

## Current references
- Existing Ralph command docs live in `.opencode/command/`.
- Existing Ralph automation lives in `.opencode/plugin/ralph.ts`.

## Planned shift
- Keep Ralph as a local Python package with a console command.
- Simplify Ralph into a thin wrapper around any CLI command.
- Use a `src/` package layout and keep tests under `tests/`.
- Keep loop control in the foreground process so `Ctrl+C` is the stop mechanism.

## Runtime dependencies
- `python`
- `uv`

## Constraints
- Prefer Python standard library modules over third-party packages.
- Use `argparse` for argument parsing.
- Use `uv` for environment setup and installation.
- Use `pytest` for tests and keep total coverage above 80%.
- Stream child stdout directly to the user's terminal.
- Keep child output unbuffered so users can follow model output in real time.
- Help output must include short usage for empty invocation, explicit completion-promise guidance, timeout scope, sleep scope, stdin passthrough, and examples.
- The wrapped command must appear after a required `--` separator.
- `start` should default to `--max-iterations 20` and `--completion-promise DONE`.
- `start` should default to `--timeout 3600` and allow `--timeout`/`-t` overrides.
- `start` should default to `--sleep 0` and allow `--sleep`/`-s` overrides.
- Ralph must not inject completion-promise instructions into the wrapped command.
- Ralph should only treat the completion promise as satisfied when the matching `<promise>...</promise>` appears on the final non-empty visible output line after terminal control codes are ignored.
- Each `opencode` iteration must use a timeout.
- Each loop iteration should run the same wrapped command.
- Ralph should pass stdin through to the wrapped command.
- `Ctrl+C` should stop Ralph directly.
- Help and version must work without starting a loop.
