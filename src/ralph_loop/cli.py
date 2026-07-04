from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import NoReturn

from .commands import build_options, run_command
from .constants import (
    DEFAULT_COMPLETION_PROMISE,
    DEFAULT_MAX_ITERATIONS,
    DEFAULT_SESSION_TIMEOUT,
    DEFAULT_TIMEOUT_SECONDS,
    VERSION,
)
from .runtime import CommandError


HELP_TEXT = (
    "Run the wrapped command in a loop.\n\n"
    "Promise:\n"
    "  ralph-loop only detects the promise. It does not add it to your prompt or input.\n"
    "  Tell the wrapped command to print <promise>DONE</promise> itself when the\n"
    "  work is truly complete.\n"
    "  ralph-loop only accepts the promise when it is the final non-empty visible line.\n\n"
    "Notes:\n"
    "  -- is required before the wrapped command.\n"
    "  --timeout applies to each iteration, not the full ralph-loop session.\n"
    "  --session-timeout applies to the entire ralph-loop session.\n"
    "  --sleep waits only between successful iterations.\n"
    "  --max-iterations 0 means run without an iteration limit.\n"
    "  ralph-loop passes stdin through to the wrapped command.\n"
    "  Piped input is not replayed between iterations.\n\n"
    "Examples:\n"
    "  ralph-loop -c DONE -- opencode run --agent vibe --model ollama/gemma4\n"
    '    "Fix the auth flow. End with <promise>DONE</promise> when the work is complete."\n'
    "  ralph-loop --max-iterations 3 --timeout 900 -- claude\n"
    '    "Review the migration and end with <promise>DONE</promise> when finished."\n'
    "  echo test | ralph-loop -i 1 -- sh -lc\n"
    "    'cat; printf \"<promise>DONE</promise>\\\\n\"'"
)


class RalphLoopHelpFormatter(argparse.RawDescriptionHelpFormatter):
    def _fill_text(self, text: str, width: int, indent: str) -> str:
        return "\n".join(
            f"{indent}{line}" if line else "" for line in text.splitlines()
        )

    def _split_lines(self, text: str, width: int) -> list[str]:
        return text.splitlines()


class RalphLoopArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        raise CommandError(f"error: {message}")


def build_parser() -> argparse.ArgumentParser:
    parser = RalphLoopArgumentParser(
        prog="ralph-loop",
        description="Loop a command until it finishes or ralph-loop stops it.",
        usage="ralph-loop [options] -- <command> [args...]",
        epilog=HELP_TEXT,
        formatter_class=RalphLoopHelpFormatter,
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
    parser.add_argument(
        "--session-timeout",
        type=int,
        default=DEFAULT_SESSION_TIMEOUT,
    )
    return parser


def main(argv: list[str] | None = None, directory: Path | None = None) -> int:
    parser = build_parser()
    args_list = list(sys.argv[1:] if argv is None else argv)

    if not args_list:
        sys.stdout.write(parser.format_usage())
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
