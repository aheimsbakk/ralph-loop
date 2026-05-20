# Ralph CLI architecture

## Goal
- Replace the standalone Bash implementation with an installable Python command named `ralph`.
- Preserve the current Ralph loop behavior: repeated prompt execution, completion promise stop, max-iteration stop, timeout stop, and manual cancellation with `Ctrl+C`.

## Files
- `./pyproject.toml` — package metadata, uv-managed dependencies, pytest configuration, console script entry.
- `./src/ralph/cli.py` — argparse entrypoint and command dispatch.
- `./src/ralph/commands.py` — command orchestration for `start` and `status`.
- `./src/ralph/runtime.py` — loop execution, live stdout streaming, signal handling, and process checks.
- `./src/ralph/state.py` — `ralph-loop.local.md` parsing and writing.
- `./src/ralph/models.py` — state and start option data models.
- `./src/ralph/constants.py` — version, defaults, and file names.
- `./tests/*.py` — pytest coverage for CLI, state, and runtime behavior.

## CLI surface
- Entry: `ralph <command> [options]`
- Commands: `start`, `status`
- Global flags: `--help`/`-h`, `--version`/`-v`
- No-argument behavior: print a short usage summary.
- Help behavior: show full command help, explain the standard contract, and print the standard injected prompt template.
- `start`: `ralph start --agent <agent> --model <model> [--max-iterations <count>] [--completion-promise <text>] [--timeout <seconds>] [--sleep <seconds>] [-s|--state-file <path>] [-P|--no-standard-prompt] <prompt>`
- `status`: `ralph status [-s|--state-file <path>]`
- Required `start` flags: `--agent`/`-a`, `--model`/`-m`
- Optional `start` flags: `--max-iterations`/`-i`, `--completion-promise`/`-c`, `--timeout`/`-t`, `--sleep`, `-s`/`--state-file`, `-P`/`--no-standard-prompt`
- Default `start` values: `--max-iterations 20`, `--completion-promise DONE`, `--timeout 3600`, `--sleep 0`

## State model
- Path: default `./ralph-loop.local.md`, override with `-s`/`--state-file`
- Front matter fields: `active`, `status`, `iteration`, `max_iterations`, `completion_promise`, `timeout_seconds`, `sleep_seconds`, `inject_standard_prompt`, `started_at`, `updated_at`, `agent`, `model`, `pid`, `last_exit_code`
- Body: saved task text without injected runtime instructions

## Runtime behavior
- `start` validates required flags, prompt presence, numeric limits, and that no live Ralph supervisor is already active.
- `start` and `status` use the selected state file path.
- By default, each iteration injects the completion-promise warning block ahead of the saved task text.
- `--no-standard-prompt` disables that injected block and sends only the saved task text.
- Each iteration runs the `opencode` CLI with the saved prompt, agent, and model through Python subprocess management.
- Each iteration uses a pseudo-terminal so child output stays unbuffered and visible in real time.
- Ralph can sleep for a configured number of seconds between successful iterations.
- Each iteration enforces a bounded timeout with Python runtime controls.
- Stop conditions: a matching `<promise>...</promise>` on the final non-empty visible output line after terminal control codes are ignored, max iterations reached, timeout failure, `Ctrl+C`, or unrecoverable command failure.
- `status` reports persisted state and whether the recorded PID is still alive.

## Compatibility
- Keep the existing promise tag format and the `./ralph-loop.local.md` file path.
- Treat `.opencode/command/*.md` and `.opencode/plugin/ralph.ts` as the behavior source for the Python version.
