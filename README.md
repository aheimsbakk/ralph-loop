# Ralph CLI

## What it is

`ralph` is an installable Python command that runs another CLI command in a loop.

## What it does

- Streams child output to your terminal in real time.
- Stops when the child prints a matching completion promise.
- Stops on a non-zero exit code, a timeout, the iteration limit, or `Ctrl+C`.
- Passes stdin through to the wrapped command.

## Install

To install `ralph` directly from GitHub:

```bash
uv tool install git+https://github.com/aheimsbakk/opencode-ralph
```

To run `ralph` directly from GitHub without installing it:

```bash
uvx --from git+https://github.com/aheimsbakk/opencode-ralph ralph --help
```

## Usage

## Quick start

```bash
ralph -c DONE -- opencode run --agent vibe --model ollama/gemini4 "Fix the auth flow. Print <promise>DONE</promise> only when the work is complete."
```

`--` is required. Everything after it is passed to the wrapped command unchanged.

## Usage

```bash
ralph [options] -- <command> [args...]
```

Examples:

```bash
ralph -c DONE -- opencode run --agent vibe --model ollama/gemini4 "Fix the auth flow. Print <promise>DONE</promise> only when the work is complete."
ralph --max-iterations 3 --timeout 900 -- claude "Review the migration and end with <promise>DONE</promise> when finished."
ralph -i 5 -s 2 -- copilot-cli "Retry the code review until it ends with <promise>DONE</promise>."
echo test | ralph -i 1 -- sh -lc 'cat; printf "<promise>DONE</promise>\n"'
```

## Promise contract

Ralph only detects the promise. It does not add extra text to your prompt or stdin.

Tell the wrapped command to print a matching promise tag itself:

```text
<promise>DONE</promise>
```

Ralph only stops on a promise when all of these are true:

- The tag matches `-c` or `--completion-promise`.
- The tag is the final non-empty visible output line.
- Terminal control codes do not change that result.
- The statement is true, because Ralph has no way to verify it for you.

Practical pattern:

```text
Do the work. When it is fully complete, end your final output line with <promise>DONE</promise>.
Do not print that tag before the work is complete.
```

## Options

- `-i`, `--max-iterations`: Stop after this many successful iterations. Use `0` for unlimited iterations. Default: `20`.
- `-c`, `--completion-promise`: Promise text Ralph waits for inside `<promise>...</promise>`. Default: `DONE`.
- `-t`, `--timeout`: Per-iteration timeout in seconds. Default: `3600`.
- `-s`, `--sleep`: Seconds to wait between successful iterations. Default: `0`.
- `-h`, `--help`: Show help.
- `-v`, `--version`: Show the Ralph version.

## Behavior

Ralph stops when one of these happens:

- The child prints the matching promise tag on its final non-empty line.
- The child exits with a non-zero code.
- The iteration times out. Ralph returns exit code `124`.
- The iteration limit is reached. Ralph returns exit code `0`.
- You press `Ctrl+C`. Ralph returns exit code `130`.

Ralph streams stdout and stderr from the child in real time through a pseudo-terminal.

Ralph passes stdin through to the wrapped command. If you pipe data into Ralph, the wrapped command can read it. Ralph does not buffer and replay that stdin for later iterations.

That means this works for the first iteration:

```bash
echo test | ralph -i 1 -- sh -lc 'cat; printf "<promise>DONE</promise>\n"'
```

If the command needs the same stdin on later iterations, you must make that data available another way, such as a file, an environment variable, or command arguments.

## Tests

```bash
uv run pytest
```
