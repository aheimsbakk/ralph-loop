from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, cast

import pytest

from ralph_loop.commands import build_options, run_command
from ralph_loop.models import IterationResult, RalphLoopOptions
from ralph_loop.runtime import CommandError, LoopInterrupted


def make_args(**overrides: object) -> argparse.Namespace:
    values: dict[str, object] = {
        "max_iterations": 20,
        "completion_promise": "COMPLETE",
        "timeout": 3600,
        "sleep": 0,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def make_options(**overrides: object) -> RalphLoopOptions:
    values: dict[str, Any] = {
        "wrapped_command": ("opencode", "run", "Prompt"),
        "max_iterations": 20,
        "completion_promise": "COMPLETE",
        "timeout_seconds": 3600,
        "sleep_seconds": 0,
    }
    values.update(overrides)
    return RalphLoopOptions(**cast(dict[str, Any], values))


def test_build_options_validates_required_fields() -> None:
    with pytest.raises(CommandError, match="--completion-promise cannot be empty"):
        build_options(make_args(completion_promise=""), ["opencode", "run"])


def test_build_options_validates_timeout() -> None:
    with pytest.raises(
        CommandError, match="--timeout must be a positive integer in seconds"
    ):
        build_options(make_args(timeout=0), ["opencode", "run"])


def test_build_options_validates_sleep() -> None:
    with pytest.raises(
        CommandError, match="--sleep must be a non-negative integer in seconds"
    ):
        build_options(make_args(sleep=-1), ["opencode", "run"])


def test_build_options_validates_iteration_limit() -> None:
    with pytest.raises(
        CommandError, match="--max-iterations must be a non-negative integer"
    ):
        build_options(make_args(max_iterations=-1), ["opencode", "run"])


def test_build_options_keeps_wrapped_command() -> None:
    options = build_options(
        make_args(), ["opencode", "run", "--model", "gpt-5", "Prompt"]
    )

    assert options.wrapped_command == (
        "opencode",
        "run",
        "--model",
        "gpt-5",
        "Prompt",
    )


def test_build_options_requires_wrapped_command() -> None:
    with pytest.raises(CommandError, match="missing wrapped command"):
        build_options(make_args(), [])


def test_run_command_completes_on_promise(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    class FakeSupervisor:
        def __init__(self, _directory: Path) -> None:
            self.installed = False

        def install_signal_handlers(self) -> None:
            self.installed = True

        def restore_signal_handlers(self) -> None:
            self.installed = False

        def run_iteration(
            self, _options: RalphLoopOptions, _iteration: int
        ) -> IterationResult:
            return IterationResult(0, "iteration 1\n<promise>COMPLETE</promise>\n")

    monkeypatch.setattr(
        "ralph_loop.commands.ensure_command_available", lambda *_args: None
    )
    monkeypatch.setattr("ralph_loop.commands.LoopSupervisor", FakeSupervisor)

    exit_code = run_command(make_options(), tmp_path)
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "ralph-loop started." in captured.out
    assert "ralph-loop completed at iteration 1." in captured.out


def test_run_command_ignores_promise_mentioned_before_final_line(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    class FakeSupervisor:
        def __init__(self, _directory: Path) -> None:
            self.calls = 0
            self.iterations: list[int] = []

        def install_signal_handlers(self) -> None:
            return None

        def restore_signal_handlers(self) -> None:
            return None

        def run_iteration(
            self, _options: RalphLoopOptions, _iteration: int
        ) -> IterationResult:
            self.calls += 1
            if self.calls == 1:
                return IterationResult(
                    0,
                    "I will only output <promise>COMPLETE</promise> when truly done.\nStill working.\n",
                )
            return IterationResult(0, "<promise>COMPLETE</promise>\n")

    monkeypatch.setattr(
        "ralph_loop.commands.ensure_command_available", lambda *_args: None
    )
    supervisor = FakeSupervisor(tmp_path)
    monkeypatch.setattr(
        "ralph_loop.commands.LoopSupervisor", lambda _directory: supervisor
    )

    exit_code = run_command(make_options(max_iterations=2), tmp_path)
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "ralph-loop completed at iteration 2." in captured.out


def test_run_command_stops_at_max_iterations(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    class FakeSupervisor:
        def __init__(self, _directory: Path) -> None:
            self.calls = 0
            self.iterations: list[int] = []

        def install_signal_handlers(self) -> None:
            return None

        def restore_signal_handlers(self) -> None:
            return None

        def run_iteration(
            self, _options: RalphLoopOptions, iteration: int
        ) -> IterationResult:
            self.calls += 1
            self.iterations.append(iteration)
            return IterationResult(0, f"iteration {self.calls}\n")

    monkeypatch.setattr(
        "ralph_loop.commands.ensure_command_available", lambda *_args: None
    )
    supervisor = FakeSupervisor(tmp_path)
    monkeypatch.setattr(
        "ralph_loop.commands.LoopSupervisor", lambda _directory: supervisor
    )

    exit_code = run_command(make_options(max_iterations=2), tmp_path)
    captured = capsys.readouterr()

    assert exit_code == 0
    assert supervisor.iterations == [1, 2]
    assert "ralph-loop stopped after 2 iterations." in captured.out


def test_run_command_sleeps_between_iterations(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    class FakeSupervisor:
        def __init__(self, _directory: Path) -> None:
            self.calls = 0

        def install_signal_handlers(self) -> None:
            return None

        def restore_signal_handlers(self) -> None:
            return None

        def run_iteration(
            self, _options: RalphLoopOptions, _iteration: int
        ) -> IterationResult:
            self.calls += 1
            return IterationResult(0, f"iteration {self.calls}\n")

    sleeps: list[int] = []
    monkeypatch.setattr(
        "ralph_loop.commands.ensure_command_available", lambda *_args: None
    )
    supervisor = FakeSupervisor(tmp_path)
    monkeypatch.setattr(
        "ralph_loop.commands.LoopSupervisor", lambda _directory: supervisor
    )
    monkeypatch.setattr(
        "ralph_loop.commands.time.sleep", lambda seconds: sleeps.append(seconds)
    )

    exit_code = run_command(make_options(max_iterations=2, sleep_seconds=3), tmp_path)

    assert exit_code == 0
    assert sleeps == [3]


def test_run_command_does_not_sleep_after_promise(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    class FakeSupervisor:
        def __init__(self, _directory: Path) -> None:
            return None

        def install_signal_handlers(self) -> None:
            return None

        def restore_signal_handlers(self) -> None:
            return None

        def run_iteration(
            self, _options: RalphLoopOptions, _iteration: int
        ) -> IterationResult:
            return IterationResult(0, "<promise>COMPLETE</promise>\n")

    sleeps: list[int] = []
    monkeypatch.setattr(
        "ralph_loop.commands.ensure_command_available", lambda *_args: None
    )
    monkeypatch.setattr("ralph_loop.commands.LoopSupervisor", FakeSupervisor)
    monkeypatch.setattr(
        "ralph_loop.commands.time.sleep", lambda seconds: sleeps.append(seconds)
    )

    exit_code = run_command(make_options(sleep_seconds=3), tmp_path)

    assert exit_code == 0
    assert sleeps == []


def test_run_command_reports_iteration_failure(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    class FakeSupervisor:
        def __init__(self, _directory: Path) -> None:
            return None

        def install_signal_handlers(self) -> None:
            return None

        def restore_signal_handlers(self) -> None:
            return None

        def run_iteration(
            self, _options: RalphLoopOptions, _iteration: int
        ) -> IterationResult:
            return IterationResult(23, "forced failure")

    monkeypatch.setattr(
        "ralph_loop.commands.ensure_command_available", lambda *_args: None
    )
    monkeypatch.setattr("ralph_loop.commands.LoopSupervisor", FakeSupervisor)

    exit_code = run_command(make_options(), tmp_path)
    captured = capsys.readouterr()

    assert exit_code == 23
    assert "command exited with code 23" in captured.err


def test_run_command_treats_sigint_exit_as_cancelled(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    class FakeSupervisor:
        def __init__(self, _directory: Path) -> None:
            return None

        def install_signal_handlers(self) -> None:
            return None

        def restore_signal_handlers(self) -> None:
            return None

        def run_iteration(
            self, _options: RalphLoopOptions, _iteration: int
        ) -> IterationResult:
            return IterationResult(130, "hello\n")

    monkeypatch.setattr(
        "ralph_loop.commands.ensure_command_available", lambda *_args: None
    )
    monkeypatch.setattr("ralph_loop.commands.LoopSupervisor", FakeSupervisor)

    exit_code = run_command(make_options(), tmp_path)
    captured = capsys.readouterr()

    assert exit_code == 130
    assert captured.err == ""


def test_run_command_marks_cancelled_on_signal(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    class FakeSupervisor:
        def __init__(self, _directory: Path) -> None:
            return None

        def install_signal_handlers(self) -> None:
            return None

        def restore_signal_handlers(self) -> None:
            return None

        def run_iteration(
            self, _options: RalphLoopOptions, _iteration: int
        ) -> IterationResult:
            raise LoopInterrupted(15)

    monkeypatch.setattr(
        "ralph_loop.commands.ensure_command_available", lambda *_args: None
    )
    monkeypatch.setattr("ralph_loop.commands.LoopSupervisor", FakeSupervisor)

    exit_code = run_command(make_options(), tmp_path)

    assert exit_code == 143


def test_run_command_reports_timeout(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    class FakeSupervisor:
        def __init__(self, _directory: Path) -> None:
            return None

        def install_signal_handlers(self) -> None:
            return None

        def restore_signal_handlers(self) -> None:
            return None

        def run_iteration(
            self, _options: RalphLoopOptions, _iteration: int
        ) -> IterationResult:
            return IterationResult(124, "slow\n")

    monkeypatch.setattr(
        "ralph_loop.commands.ensure_command_available", lambda *_args: None
    )
    monkeypatch.setattr("ralph_loop.commands.LoopSupervisor", FakeSupervisor)

    exit_code = run_command(make_options(timeout_seconds=12), tmp_path)
    captured = capsys.readouterr()

    assert exit_code == 124
    assert "iteration timed out after 12s" in captured.err
