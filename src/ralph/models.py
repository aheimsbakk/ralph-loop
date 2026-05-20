from __future__ import annotations

from dataclasses import dataclass

from .constants import (
    DEFAULT_COMPLETION_PROMISE,
    DEFAULT_MAX_ITERATIONS,
    DEFAULT_TIMEOUT_SECONDS,
)


@dataclass(slots=True)
class StartOptions:
    agent: str
    model: str
    prompt: str
    state_file: str
    max_iterations: int = DEFAULT_MAX_ITERATIONS
    completion_promise: str = DEFAULT_COMPLETION_PROMISE
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS
    sleep_seconds: int = 0
    inject_standard_prompt: bool = True


@dataclass(slots=True)
class RalphState:
    active: bool = False
    status: str | None = None
    iteration: int = 0
    max_iterations: int = 0
    completion_promise: str | None = None
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS
    sleep_seconds: int = 0
    inject_standard_prompt: bool = True
    started_at: str | None = None
    updated_at: str | None = None
    agent: str | None = None
    model: str | None = None
    pid: int | None = None
    last_exit_code: int | None = None
    prompt: str = ""


@dataclass(slots=True)
class IterationResult:
    exit_code: int
    output: str
