# Project context

## Current references
- Existing Ralph command docs live in `.opencode/command/`.
- Existing Ralph automation lives in `.opencode/plugin/ralph.ts`.
- The current local Ralph state example is `./ralph-loop.local.md`.

## Planned shift
- Move Ralph orchestration from the Bash script into a local Python package with a console command.
- Keep the same user-facing concepts, but run each loop iteration through the `opencode` CLI.
- Use a `src/` package layout and keep tests under `tests/`.
- Keep loop control in the foreground process so `Ctrl+C` is the stop mechanism.

## Runtime dependencies
- `python`
- `uv`
- `opencode` CLI

## Constraints
- Prefer Python standard library modules over third-party packages.
- Use `argparse` for argument parsing.
- Use `uv` for environment setup and installation.
- Use `pytest` for tests and keep total coverage above 80%.
- Stream child stdout directly to the user's terminal.
- Keep child output unbuffered so users can follow model output in real time.
- Help output must include short usage for empty invocation, explicit completion-promise guidance, and the standard injected prompt contract.
- Supported `opencode` root options placed before `start`, `status`, or `help` must pass through unchanged to loop iterations, except Ralph's own `--help` and `--version`.
- `start` must require `--agent`/`-a` and `--model`/`-m`.
- `start` should default to `--max-iterations 20` and `--completion-promise DONE`.
- `start` should default to `--timeout 3600` and allow `--timeout`/`-t` overrides.
- `start` should default to `--sleep 0` and allow `--sleep` overrides.
- `start` and `status` should default to `./ralph-loop.local.md` and allow `-s`/`--state-file` overrides.
- Ralph must inject the completion-promise instructions into each runtime prompt automatically unless `-P` or `--no-standard-prompt` is set.
- Ralph should only treat the completion promise as satisfied when the matching `<promise>...</promise>` appears on the final non-empty visible output line after terminal control codes are ignored.
- Each `opencode` iteration must use a timeout.
- `Ctrl+C` should replace the dedicated cancel command.
- Help and version must work without starting a loop.
- `status` must rely on persisted local state.
