from __future__ import annotations

import argparse
from pathlib import Path
import shlex
import sys
import time

from .models import RalphOptions
from .runtime import (
    CommandError,
    LoopInterrupted,
    LoopSupervisor,
    ensure_command_available,
    promise_detected,
    signal_exit_code,
)


def build_options(args: argparse.Namespace, wrapped_command: list[str]) -> RalphOptions:
    completion_promise = _require_text(args.completion_promise, "--completion-promise")
    if args.max_iterations < 0:
        raise CommandError("--max-iterations must be a non-negative integer")
    if args.timeout <= 0:
        raise CommandError("--timeout must be a positive integer in seconds")
    if args.sleep < 0:
        raise CommandError("--sleep must be a non-negative integer in seconds")
    command = _wrapped_command(wrapped_command)

    return RalphOptions(
        wrapped_command=command,
        max_iterations=args.max_iterations,
        completion_promise=completion_promise,
        timeout_seconds=args.timeout,
        sleep_seconds=args.sleep,
    )


def run_command(options: RalphOptions, directory: Path) -> int:
    ensure_command_available(options.wrapped_command, directory)
    _print_start_banner(options)

    supervisor = LoopSupervisor(directory)
    supervisor.install_signal_handlers()
    try:
        iteration = 1
        while True:
            result = supervisor.run_iteration(options, iteration)

            if result.exit_code != 0:
                if result.exit_code == 124:
                    print(
                        f"Ralph loop stopped: iteration timed out after {options.timeout_seconds}s.",
                        file=sys.stderr,
                    )
                elif result.exit_code == 130:
                    return 130
                else:
                    print(
                        f"Ralph loop stopped: command exited with code {result.exit_code}.",
                        file=sys.stderr,
                    )
                return result.exit_code

            if promise_detected(result.output, options.completion_promise):
                print(f"Ralph loop completed at iteration {iteration}.")
                return 0

            if options.max_iterations > 0 and iteration >= options.max_iterations:
                print(f"Ralph loop stopped after {options.max_iterations} iterations.")
                return 0

            if options.sleep_seconds > 0:
                time.sleep(options.sleep_seconds)

            iteration += 1
    except LoopInterrupted as error:
        return signal_exit_code(error.signum)
    finally:
        supervisor.restore_signal_handlers()


def _require_text(value: str | None, label: str) -> str:
    if value is None or not value.strip():
        raise CommandError(f"{label} cannot be empty")
    return value.strip()


def _iteration_limit_label(max_iterations: int) -> str:
    return "unlimited" if max_iterations == 0 else str(max_iterations)


def _print_start_banner(options: RalphOptions) -> None:
    print("Ralph loop started.")
    print()
    print(f"Command: {shlex.join(options.wrapped_command)}")
    print(f"Iteration limit: {_iteration_limit_label(options.max_iterations)}")
    print(f"Per-iteration timeout: {options.timeout_seconds}s")
    print(f"Sleep between iterations: {options.sleep_seconds}s")
    print(f"Completion promise: {options.completion_promise}")
    print()
    print("Stop conditions:")
    print(
        f"  - Final non-empty visible line is <promise>{options.completion_promise}</promise>"
    )
    print("  - Reach the iteration limit")
    print("  - Wrapped command exits with a non-zero code")
    print("  - An iteration times out")
    print("  - Press Ctrl+C")


def _wrapped_command(command: list[str]) -> tuple[str, ...]:
    if not command:
        raise CommandError("error: missing wrapped command after '--'")
    if not all(isinstance(item, str) and item for item in command):
        raise CommandError("wrapped command arguments must be non-empty strings")
    return tuple(command)
