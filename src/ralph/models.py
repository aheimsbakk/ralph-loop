from __future__ import annotations

from dataclasses import dataclass

from .constants import (
    DEFAULT_COMPLETION_PROMISE,
    DEFAULT_MAX_ITERATIONS,
    DEFAULT_TIMEOUT_SECONDS,
)


@dataclass(slots=True)
class RalphOptions:
    wrapped_command: tuple[str, ...]
    max_iterations: int = DEFAULT_MAX_ITERATIONS
    completion_promise: str = DEFAULT_COMPLETION_PROMISE
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS
    sleep_seconds: int = 0


@dataclass(slots=True)
class IterationResult:
    exit_code: int
    output: str
