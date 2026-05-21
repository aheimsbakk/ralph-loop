from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import NoReturn

from .commands import build_options, run_command
from .constants import (
    DEFAULT_COMPLETION_PROMISE,
    DEFAULT_MAX_ITERATIONS,
    DEFAULT_TIMEOUT_SECONDS,
    VERSION,
)
from .runtime import CommandError


SHORT_USAGE_TEXT = """Usage:
  ralph [options] -- <command> [args...]
  ralph --help
  ralph --version"""

HELP_TEXT = """Run the wrapped command in a Ralph loop.

Promise:
  Ralph only detects the promise. It does not add it to your prompt or input.
  Tell the wrapped command to print <promise>DONE</promise> itself when the
  work is truly complete.
  Ralph only accepts the promise when it is the final non-empty visible line.

Notes:
  -- is required before the wrapped command.
  --timeout applies to each iteration, not the full Ralph session.
  --sleep waits only between successful iterations.
  --max-iterations 0 means run without an iteration limit.
  Ralph passes stdin through to the wrapped command.
  Piped input is not replayed between iterations.

Examples:
  ralph -c DONE -- opencode run --agent vibe --model ollama/gemini4 "Fix the
  auth flow. End with <promise>DONE</promise> when the work is complete."
  ralph --max-iterations 3 --timeout 900 -- claude "Review the migration and
  end with <promise>DONE</promise> when finished."
  echo test | ralph -i 1 -- sh -lc 'cat; printf "<promise>DONE</promise>\n"'"""


class RalphArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        raise CommandError(f"error: {message}")


def build_parser() -> argparse.ArgumentParser:
    parser = RalphArgumentParser(
        prog="ralph",
        description="Loop a command until it finishes or Ralph stops it.",
        usage="ralph [options] -- <command> [args...]",
        epilog=HELP_TEXT,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "-v", "--version", action="version", version=f"%(prog)s {VERSION}"
    )
    parser.add_argument(
        "-i", "--max-iterations", type=int, default=DEFAULT_MAX_ITERATIONS
    )
    parser.add_argument(
        "-c", "--completion-promise", default=DEFAULT_COMPLETION_PROMISE
    )
    parser.add_argument("-t", "--timeout", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("-s", "--sleep", type=int, default=0)
    return parser


def main(argv: list[str] | None = None, directory: Path | None = None) -> int:
    parser = build_parser()
    args_list = list(sys.argv[1:] if argv is None else argv)

    if not args_list:
        print(SHORT_USAGE_TEXT)
        return 0

    try:
        separator_index = _separator_index(args_list)
        parser_args = (
            args_list if separator_index is None else args_list[:separator_index]
        )
        wrapped_command = (
            [] if separator_index is None else args_list[separator_index + 1 :]
        )
        args = parser.parse_args(parser_args)
        if separator_index is None:
            raise CommandError("error: missing command separator '--'")
        options = build_options(args, wrapped_command)
        return run_command(options, Path.cwd() if directory is None else directory)
    except CommandError as error:
        print(error.message, file=sys.stderr)
        return error.exit_code


def _separator_index(args_list: list[str]) -> int | None:
    for index, token in enumerate(args_list):
        if token == "--":
            return index
    return None
