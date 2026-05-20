from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import NoReturn

from .commands import PROMISE_TEMPLATE, start_command, status_command
from .constants import (
    DEFAULT_COMPLETION_PROMISE,
    DEFAULT_MAX_ITERATIONS,
    DEFAULT_TIMEOUT_SECONDS,
    VERSION,
)
from .runtime import CommandError


USAGE_TEXT = """Usage:
  ralph [opencode-options...] <command> [options]
  ralph start -a AGENT -m MODEL [options] <prompt>
  ralph status [options]
  ralph help [start|status]
  ralph --help
  ralph --version"""

COMMAND_NAMES = frozenset({"start", "status", "help"})
PASSTHROUGH_OPTIONS: dict[str, bool] = {
    "--print-logs": False,
    "--log-level": True,
    "--pure": False,
    "--port": True,
    "--hostname": True,
    "--mdns": False,
    "--mdns-domain": True,
    "--cors": True,
    "-m": True,
    "--model": True,
    "-c": False,
    "--continue": False,
    "-s": True,
    "--session": True,
    "--fork": False,
    "--prompt": True,
    "--agent": True,
}
RALPH_GLOBAL_OPTIONS = frozenset({"-h", "--help", "-v", "--version"})

PROMISE_GUIDANCE = f"""Hint: add the same completion promise to your prompt.

This is the standard contract Ralph injects before your task.
You can use it as-is or improve on it in your own prompt text.

Standard injected prompt template:

{PROMISE_TEMPLATE}"""


class RalphArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        raise CommandError(f"error: {message}")


def build_parser() -> tuple[
    argparse.ArgumentParser, dict[str, argparse.ArgumentParser]
]:
    parser = RalphArgumentParser(
        prog="ralph",
        description="Run Ralph Wiggum loops with OpenCode.",
        usage=USAGE_TEXT,
        epilog=PROMISE_GUIDANCE,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "-v", "--version", action="version", version=f"%(prog)s {VERSION}"
    )

    subparsers = parser.add_subparsers(dest="command")
    parsers: dict[str, argparse.ArgumentParser] = {}

    start_parser = subparsers.add_parser(
        "start",
        help="Start a Ralph loop",
        usage="ralph start -a AGENT -m MODEL [options] <prompt>",
        epilog=PROMISE_GUIDANCE,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Start a Ralph loop.",
    )
    start_parser.add_argument("-a", "--agent")
    start_parser.add_argument("-m", "--model")
    start_parser.add_argument(
        "-i", "--max-iterations", type=int, default=DEFAULT_MAX_ITERATIONS
    )
    start_parser.add_argument(
        "-c", "--completion-promise", default=DEFAULT_COMPLETION_PROMISE
    )
    start_parser.add_argument(
        "-t", "--timeout", type=int, default=DEFAULT_TIMEOUT_SECONDS
    )
    start_parser.add_argument("--sleep", type=int, default=0)
    start_parser.add_argument("-s", "--state-file", default="ralph-loop.local.md")
    start_parser.add_argument("-P", "--no-standard-prompt", action="store_true")
    start_parser.add_argument("prompt", nargs="*")
    parsers["start"] = start_parser

    status_parser = subparsers.add_parser(
        "status",
        help="Show Ralph loop status",
        usage="ralph status [-s STATE_FILE]",
    )
    status_parser.add_argument("-s", "--state-file", default="ralph-loop.local.md")
    parsers["status"] = status_parser

    help_parser = subparsers.add_parser(
        "help",
        help="Show general or command help",
        usage="ralph help [start|status]",
    )
    help_parser.add_argument("topic", nargs="?")
    parsers["help"] = help_parser

    parsers["__root__"] = parser

    return parser, parsers


def main(argv: list[str] | None = None, directory: Path | None = None) -> int:
    parser, parsers = build_parser()
    args_list = list(sys.argv[1:] if argv is None else argv)

    if not args_list:
        print(USAGE_TEXT)
        return 0

    try:
        opencode_args, parser_args = split_pre_command_args(args_list)
        if not parser_args:
            raise CommandError("error: missing command")
        args = parser.parse_args(parser_args)
        args.opencode_args = opencode_args
        return _dispatch(
            args, parser, parsers, Path.cwd() if directory is None else directory
        )
    except CommandError as error:
        print(error.message, file=sys.stderr)
        return error.exit_code


def _dispatch(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
    parsers: dict[str, argparse.ArgumentParser],
    directory: Path,
) -> int:
    if args.command is None:
        parser.print_help()
        return 0

    if args.command == "help":
        target = parsers["__root__"] if not args.topic else parsers.get(args.topic)
        if target is None:
            raise CommandError(f"unknown help topic: {args.topic}")
        target.print_help()
        return 0

    if args.command == "start":
        return start_command(args, directory)
    if args.command == "status":
        return status_command(args, directory)

    raise CommandError(f"unknown command: {args.command}")


def split_pre_command_args(args_list: list[str]) -> tuple[list[str], list[str]]:
    opencode_args: list[str] = []
    index = 0

    while index < len(args_list):
        token = args_list[index]
        if token in COMMAND_NAMES:
            return opencode_args, args_list[index:]
        if token in RALPH_GLOBAL_OPTIONS:
            return opencode_args, args_list[index:]

        option = _match_passthrough_option(token)
        if option is None:
            return opencode_args, args_list[index:]

        name, expects_value = option
        opencode_args.append(token)
        index += 1

        if not expects_value or _has_inline_value(token):
            continue

        if index >= len(args_list):
            raise CommandError(f"missing value for opencode option: {name}")

        opencode_args.append(args_list[index])
        index += 1

    return opencode_args, []


def _match_passthrough_option(token: str) -> tuple[str, bool] | None:
    if token in PASSTHROUGH_OPTIONS:
        return token, PASSTHROUGH_OPTIONS[token]
    if token.startswith("--"):
        name, separator, _value = token.partition("=")
        if separator and name in PASSTHROUGH_OPTIONS:
            return name, PASSTHROUGH_OPTIONS[name]
    return None


def _has_inline_value(token: str) -> bool:
    return token.startswith("--") and "=" in token
