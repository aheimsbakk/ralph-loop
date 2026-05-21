# ralph-loop CLI

## What it is

`ralph-loop` is an installable Python command that runs another CLI command in a loop.

## What it does

- Streams child output to your terminal in real time.
- Stops when the child prints a matching completion promise.
- Stops on a non-zero exit code, a timeout, the iteration limit, or `Ctrl+C`.
- Passes stdin through to the wrapped command.

## Install

To install `ralph-loop` directly from GitHub:

```bash
uv tool install git+https://github.com/aheimsbakk/ralph-loop
```

To run `ralph-loop` directly from GitHub without installing it:

```bash
uvx --from git+https://github.com/aheimsbakk/ralph-loop ralph-loop --help
```

## Quick start

```bash
ralph-loop -c DONE -- opencode run --agent vibe --model ollama/gemini4 "Fix the auth flow. Print <promise>DONE</promise> only when the work is complete."
```

`--` is required. Everything after it is passed to the wrapped command unchanged.

## Usage

```bash
ralph-loop [options] -- <command> [args...]
```

Examples:

```bash
ralph-loop -c DONE -- opencode run --agent vibe --model ollama/gemini4 "Fix the auth flow. Print <promise>DONE</promise> only when the work is complete."
ralph-loop --max-iterations 3 --timeout 900 -- claude "Review the migration and end with <promise>DONE</promise> when finished."
ralph-loop -i 5 -s 2 -- copilot-cli "Retry the code review until it ends with <promise>DONE</promise>."
echo test | ralph-loop -i 1 -- sh -lc 'cat; printf "<promise>DONE</promise>\n"'
```

## Promise contract

ralph-loop only detects the promise. It does not add extra text to your prompt or stdin.

Tell the wrapped command to print a matching promise tag itself:

```text
<promise>DONE</promise>
```

ralph-loop only stops on a promise when all of these are true:

- The tag matches `-c` or `--completion-promise`.
- The tag is the final non-empty visible output line.
- Terminal control codes do not change that result.
- The statement is true, because ralph-loop has no way to verify it for you.

Practical pattern:

```text
Do the work. When it is fully complete, end your final output line with <promise>DONE</promise>.
Do not print that tag before the work is complete.
```

## Options

- `-i`, `--max-iterations`: Stop after this many successful iterations. Use `0` for unlimited iterations. Default: `20`.
- `-c`, `--completion-promise`: Promise text ralph-loop waits for inside `<promise>...</promise>`. Default: `DONE`.
- `-t`, `--timeout`: Per-iteration timeout in seconds. Default: `3600`.
- `-s`, `--sleep`: Seconds to wait between successful iterations. Default: `0`.
- `-h`, `--help`: Show help.
- `-v`, `--version`: Show the ralph-loop version.

## Behavior

ralph-loop stops when one of these happens:

- The child prints the matching promise tag on its final non-empty line.
- The child exits with a non-zero code.
- The iteration times out. ralph-loop returns exit code `124`.
- The iteration limit is reached. ralph-loop returns exit code `0`.
- You press `Ctrl+C`. ralph-loop returns exit code `130`.

ralph-loop streams stdout and stderr from the child in real time through a pseudo-terminal.

ralph-loop passes stdin through to the wrapped command. If you pipe data into ralph-loop, the wrapped command can read it. ralph-loop does not buffer and replay that stdin for later iterations.

That means this works for the first iteration:

```bash
echo test | ralph-loop -i 1 -- sh -lc 'cat; printf "<promise>DONE</promise>\n"'
```

If the command needs the same stdin on later iterations, you must make that data available another way, such as a file, an environment variable, or command arguments.

## Tests

```bash
uv run pytest
```
