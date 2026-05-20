from __future__ import annotations

import argparse
from dataclasses import replace
import os
from pathlib import Path
import sys
import time

from .constants import STATE_FILE
from .models import RalphState, StartOptions
from .runtime import (
    CommandError,
    LoopInterrupted,
    LoopSupervisor,
    ensure_runtime_dependencies,
    is_ralph_process,
    signal_exit_code,
)
from .state import load_state, promise_detected, save_state, state_path, timestamp


PROMISE_TEMPLATE = """CRITICAL - Ralph Loop Completion Promise

To complete this loop, output this EXACT text:
  <promise>{promise}</promise>

STRICT REQUIREMENTS:
  - Use <promise> XML tags EXACTLY as shown above
  - The statement MUST be completely and unequivocally TRUE
  - Do NOT output false statements to exit the loop
  - Do NOT lie even if you think you should exit

IMPORTANT: Even if you believe you're stuck or the task is impossible,
you MUST NOT output a false promise nor say the original promise.
The loop continues until the promise is GENUINELY TRUE.

The task is:
{task}"""


def build_start_options(args: argparse.Namespace) -> StartOptions:
    agent = _require_text(args.agent, "--agent")
    model = _require_text(args.model, "--model")
    completion_promise = _require_text(args.completion_promise, "--completion-promise")
    prompt = _require_text(" ".join(args.prompt).strip(), "prompt")

    if args.max_iterations < 0:
        raise CommandError("--max-iterations must be a non-negative integer")
    if args.timeout <= 0:
        raise CommandError("--timeout must be a positive integer in seconds")
    if args.sleep < 0:
        raise CommandError("--sleep must be a non-negative integer in seconds")

    return StartOptions(
        agent=agent,
        model=model,
        prompt=prompt,
        state_file=_require_text(args.state_file, "--state-file"),
        opencode_args=tuple(_opencode_args(args)),
        max_iterations=args.max_iterations,
        completion_promise=completion_promise,
        timeout_seconds=args.timeout,
        sleep_seconds=args.sleep,
        inject_standard_prompt=not args.no_standard_prompt,
    )


def start_command(args: argparse.Namespace, directory: Path) -> int:
    options = build_start_options(args)
    ensure_runtime_dependencies()

    existing_state = load_state(directory, options.state_file)
    if (
        existing_state
        and existing_state.active
        and is_ralph_process(existing_state.pid)
    ):
        raise CommandError(
            f"an active Ralph loop is already running with PID {existing_state.pid}"
        )

    started_at = timestamp()
    state = RalphState(
        active=True,
        status="running",
        iteration=1,
        max_iterations=options.max_iterations,
        completion_promise=options.completion_promise,
        timeout_seconds=options.timeout_seconds,
        sleep_seconds=options.sleep_seconds,
        inject_standard_prompt=options.inject_standard_prompt,
        started_at=started_at,
        updated_at=started_at,
        agent=options.agent,
        model=options.model,
        opencode_args=options.opencode_args,
        pid=os.getpid(),
        prompt=options.prompt,
    )
    save_state(directory, state, options.state_file)
    _print_start_banner(directory, state, options.state_file)

    supervisor = LoopSupervisor(directory)
    supervisor.install_signal_handlers()
    try:
        while True:
            state.active = True
            state.status = "running"
            state.updated_at = timestamp()
            state.pid = os.getpid()
            save_state(directory, state, options.state_file)

            runtime_state = replace(state, prompt=_build_runtime_prompt(state))
            result = supervisor.run_iteration(runtime_state)
            state.last_exit_code = result.exit_code
            state.updated_at = timestamp()
            save_state(directory, state, options.state_file)

            if result.exit_code != 0:
                failure_status = "cancelled" if result.exit_code == 130 else "failed"
                _mark_state(
                    directory,
                    state,
                    options.state_file,
                    active=False,
                    status=failure_status,
                )
                if result.exit_code == 124:
                    print(
                        f"Ralph loop stopped: iteration timed out after {state.timeout_seconds}s.",
                        file=sys.stderr,
                    )
                elif result.exit_code == 130:
                    return 130
                else:
                    print(
                        f"Ralph loop stopped: opencode exited with code {result.exit_code}.",
                        file=sys.stderr,
                    )
                return result.exit_code

            if promise_detected(result.output, state.completion_promise):
                _mark_state(
                    directory,
                    state,
                    options.state_file,
                    active=False,
                    status="completed",
                )
                print(f"Ralph loop completed at iteration {state.iteration}.")
                return 0

            if state.max_iterations > 0 and state.iteration >= state.max_iterations:
                _mark_state(
                    directory,
                    state,
                    options.state_file,
                    active=False,
                    status="max_iterations_reached",
                )
                print(f"Ralph loop stopped after {state.max_iterations} iterations.")
                return 0

            if state.sleep_seconds > 0:
                time.sleep(state.sleep_seconds)

            state.iteration += 1
    except LoopInterrupted as error:
        latest_state = load_state(directory, options.state_file) or state
        if latest_state.active and (
            latest_state.pid is None or latest_state.pid == os.getpid()
        ):
            latest_state.last_exit_code = signal_exit_code(error.signum)
            _mark_state(
                directory,
                latest_state,
                options.state_file,
                active=False,
                status="cancelled",
            )
        return signal_exit_code(error.signum)
    finally:
        supervisor.restore_signal_handlers()


def status_command(_args: object, directory: Path) -> int:
    state_file = _state_file_option(_args)
    state = load_state(directory, state_file)
    if state is None:
        print("No Ralph loop state found.")
        return 1

    process_running = is_ralph_process(state.pid)
    print(
        "\n".join(
            [
                f"State file: {state_path(directory, state_file)}",
                f"Status: {_derived_status(state, process_running)}",
                f"Active: {str(state.active).lower()}",
                f"Iteration: {state.iteration}",
                f"Iteration limit: {_iteration_limit_label(state.max_iterations)}",
                f"Iteration timeout: {state.timeout_seconds}s",
                f"Sleep between iterations: {state.sleep_seconds}s",
                f"Standard prompt injection: {'enabled' if state.inject_standard_prompt else 'disabled'}",
                f"Completion promise: {state.completion_promise or 'none'}",
                f"Agent: {state.agent or 'unknown'}",
                f"Model: {state.model or 'unknown'}",
                f"OpenCode options: {' '.join(state.opencode_args) if state.opencode_args else 'none'}",
                f"PID: {state.pid or 'none'}",
                f"Process: {'running' if process_running else 'not running'}",
                f"Started at: {state.started_at or 'unknown'}",
                f"Updated at: {state.updated_at or 'unknown'}",
                f"Last exit code: {state.last_exit_code if state.last_exit_code is not None else 'n/a'}",
                "Prompt:",
                state.prompt,
            ]
        )
    )
    return 0


def _require_text(value: str | None, label: str) -> str:
    if value is None or not value.strip():
        raise CommandError(f"{label} cannot be empty")
    return value.strip()


def _derived_status(state: RalphState, process_running: bool) -> str:
    if state.active:
        return "running" if process_running else "stale"
    return state.status or "inactive"


def _iteration_limit_label(max_iterations: int) -> str:
    return "unlimited" if max_iterations == 0 else str(max_iterations)


def _mark_state(
    directory: Path,
    state: RalphState,
    state_file: str,
    *,
    active: bool,
    status: str,
) -> None:
    state.active = active
    state.status = status
    state.updated_at = timestamp()
    save_state(directory, state, state_file)


def _print_start_banner(directory: Path, state: RalphState, state_file: str) -> None:
    print("Ralph loop started.")
    print()
    print(f"Agent: {state.agent}")
    print(f"Model: {state.model}")
    print(f"Iteration limit: {_iteration_limit_label(state.max_iterations)}")
    print(f"Iteration timeout: {state.timeout_seconds}s")
    print(f"Sleep between iterations: {state.sleep_seconds}s")
    print(
        f"Standard prompt injection: {'enabled' if state.inject_standard_prompt else 'disabled'}"
    )
    print(f"Completion promise: {state.completion_promise}")
    print(f"State file: {state_path(directory, state_file)}")
    print()
    print("Stop conditions:")
    print(f"  - Output <promise>{state.completion_promise}</promise>")
    print("  - Reach the iteration limit")
    print("  - Press Ctrl+C")


def _build_runtime_prompt(state: RalphState) -> str:
    if not state.inject_standard_prompt:
        return state.prompt

    promise = state.completion_promise or ""
    return PROMISE_TEMPLATE.format(promise=promise, task=state.prompt)


def _state_file_option(args: object) -> str:
    value = getattr(args, "state_file", STATE_FILE)
    if not isinstance(value, str) or not value.strip():
        raise CommandError("--state-file cannot be empty")
    return value.strip()


def _opencode_args(args: object) -> list[str]:
    value = getattr(args, "opencode_args", [])
    if not isinstance(value, list):
        raise CommandError("opencode options must be a list")
    if not all(isinstance(item, str) for item in value):
        raise CommandError("opencode options must be strings")
    return value
