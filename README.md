# Ralph CLI

## What it is

`ralph` is an installable Python command that runs the same OpenCode prompt in a loop.
It streams child stdout to your terminal with unbuffered real-time output.

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

### Start a loop

```bash
ralph start -a vibe -m ollama/gemini4 "Build the API"
ralph start -a vibe -m ollama/gemini4 -i 5 -c DONE -t 1800 "Add tests"
ralph start -a vibe -m ollama/gemini4 --sleep 2 "Retry with a pause between loops"
ralph start -a vibe -m ollama/gemini4 -s custom-state.md "Use a custom state file"
ralph start -a vibe -m ollama/gemini4 -P "Use only my raw task text"
```

Press `Ctrl+C` to stop a running loop.
Ralph injects the completion-promise instructions into each loop automatically.
Use `-P` or `--no-standard-prompt` to disable that injected block.
Run `ralph help start` to see the standard contract and template.
Ralph only stops when the final non-empty visible output line is exactly the matching promise tag.
Terminal control codes from streamed model output are ignored during that check.

Example:

```bash
ralph start -a vibe -m ollama/gemini4 -c DONE "Fix the auth flow. Output <promise>DONE</promise> only when the work is fully complete."
```

Defaults:

- `-i`, `--max-iterations`: `20`
- `-c`, `--completion-promise`: `DONE`
- `-t`, `--timeout`: `3600`
- `--sleep`: `0`

### Check status

```bash
ralph status
ralph status -s custom-state.md
```

## State file

By default, the command saves state in `ralph-loop.local.md` in the project root.
Use `-s` or `--state-file` on `start` and `status` to override that path.

## Tests

```bash
uv run pytest
```
