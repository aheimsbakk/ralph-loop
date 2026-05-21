# ralph-loop architecture

## Goal
- Keep ralph-loop as an installable Python command named `ralph-loop`.
- Make ralph-loop a thin loop wrapper around any CLI command.
- Preserve repeated execution, completion promise stop, max-iteration stop, timeout stop, and manual cancellation with `Ctrl+C`.

## Files
- `./pyproject.toml` — package metadata, uv-managed dependencies, pytest configuration, console script entry.
- `./src/ralph_loop/cli.py` — argparse entrypoint and `--` command split.
- `./src/ralph_loop/commands.py` — loop orchestration and option validation.
- `./src/ralph_loop/runtime.py` — loop execution, live streaming, signal handling, timeout control, and promise detection.
- `./src/ralph_loop/models.py` — wrapper option and iteration result models.
- `./src/ralph_loop/constants.py` — version and default values.
- `./tests/*.py` — pytest coverage for CLI, loop behavior, and runtime behavior.

## CLI surface
- Entry: `ralph-loop [options] -- <command> [args...]`
- Global flags: `--help`/`-h`, `--version`/`-v`
- ralph-loop flags: `--max-iterations`/`-i`, `--completion-promise`/`-c`, `--timeout`/`-t`, `--sleep`/`-s`
- The `--` separator is required.
- No-argument behavior: print a short usage summary.
- Help behavior: explain the promise contract, timeout scope, sleep scope, stdin passthrough, and show examples.
- Default values: `--max-iterations 20`, `--completion-promise DONE`, `--timeout 3600`, `--sleep 0`

## Runtime behavior
- ralph-loop validates numeric limits and wrapped command presence before the loop starts.
- Each iteration runs the wrapped command unchanged through Python subprocess management.
- Each iteration uses a pseudo-terminal so child output stays unbuffered and visible in real time.
- ralph-loop passes stdin through to the child command.
- ralph-loop can sleep for a configured number of seconds between successful iterations.
- Each iteration enforces a bounded timeout with Python runtime controls.
- Stop conditions: a matching `<promise>...</promise>` on the final non-empty visible output line after terminal control codes are ignored, max iterations reached, timeout failure, `Ctrl+C`, or child command failure.

## Compatibility
- Keep the existing promise tag format.
- Treat `.opencode/command/*.md` and `.opencode/plugin/ralph.ts` as historical references only.
