from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from ralph.commands import (
    _build_runtime_prompt,
    build_start_options,
    start_command,
    status_command,
)
from ralph.models import IterationResult, RalphState
from ralph.runtime import CommandError, LoopInterrupted
from ralph.state import load_state, save_state


def make_start_args(**overrides: object) -> argparse.Namespace:
    values: dict[str, object] = {
        "agent": "vibe",
        "model": "ollama/gemini4",
        "max_iterations": 20,
        "completion_promise": "COMPLETE",
        "timeout": 3600,
        "sleep": 0,
        "state_file": "ralph-loop.local.md",
        "no_standard_prompt": False,
        "prompt": ["Build", "docs"],
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def test_build_start_options_validates_required_fields() -> None:
    with pytest.raises(CommandError, match="--agent cannot be empty"):
        build_start_options(make_start_args(agent=""))


def test_build_start_options_validates_timeout() -> None:
    with pytest.raises(
        CommandError, match="--timeout must be a positive integer in seconds"
    ):
        build_start_options(make_start_args(timeout=0))


def test_build_start_options_validates_sleep() -> None:
    with pytest.raises(
        CommandError, match="--sleep must be a non-negative integer in seconds"
    ):
        build_start_options(make_start_args(sleep=-1))


def test_build_start_options_keeps_custom_state_file() -> None:
    options = build_start_options(make_start_args(state_file="custom-state.md"))

    assert options.state_file == "custom-state.md"


def test_start_command_completes_on_promise(
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

        def run_iteration(self, _state: RalphState) -> IterationResult:
            return IterationResult(0, "iteration 1\n<promise>COMPLETE</promise>\n")

    monkeypatch.setattr("ralph.commands.ensure_runtime_dependencies", lambda: None)
    monkeypatch.setattr("ralph.commands.LoopSupervisor", FakeSupervisor)
    monkeypatch.setattr("ralph.commands.is_ralph_process", lambda _pid: False)

    exit_code = start_command(make_start_args(), tmp_path)
    state = load_state(tmp_path)
    captured = capsys.readouterr()

    assert exit_code == 0
    assert state is not None
    assert state.status == "completed"
    assert "Ralph loop started." in captured.out
    assert "Ralph loop completed at iteration 1." in captured.out


def test_start_command_ignores_promise_mentioned_before_final_line(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    class FakeSupervisor:
        def __init__(self, _directory: Path) -> None:
            self.calls = 0

        def install_signal_handlers(self) -> None:
            return None

        def restore_signal_handlers(self) -> None:
            return None

        def run_iteration(self, _state: RalphState) -> IterationResult:
            self.calls += 1
            if self.calls == 1:
                return IterationResult(
                    0,
                    "I will only output <promise>COMPLETE</promise> when truly done.\nStill working.\n",
                )
            return IterationResult(0, "<promise>COMPLETE</promise>\n")

    monkeypatch.setattr("ralph.commands.ensure_runtime_dependencies", lambda: None)
    supervisor = FakeSupervisor(tmp_path)
    monkeypatch.setattr("ralph.commands.LoopSupervisor", lambda _directory: supervisor)
    monkeypatch.setattr("ralph.commands.is_ralph_process", lambda _pid: False)

    exit_code = start_command(make_start_args(max_iterations=2), tmp_path)
    state = load_state(tmp_path)
    captured = capsys.readouterr()

    assert exit_code == 0
    assert state is not None
    assert state.status == "completed"
    assert state.iteration == 2
    assert "Ralph loop completed at iteration 2." in captured.out


def test_build_runtime_prompt_injects_promise_and_task() -> None:
    state = RalphState(completion_promise="DONE", prompt="Fix auth")

    prompt = _build_runtime_prompt(state)

    assert "CRITICAL - Ralph Loop Completion Promise" in prompt
    assert "<promise>DONE</promise>" in prompt
    assert prompt.endswith("The task is:\nFix auth")


def test_build_runtime_prompt_can_skip_standard_prompt() -> None:
    state = RalphState(
        completion_promise="DONE",
        prompt="Fix auth",
        inject_standard_prompt=False,
    )

    prompt = _build_runtime_prompt(state)

    assert prompt == "Fix auth"


def test_start_command_stops_at_max_iterations(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    class FakeSupervisor:
        def __init__(self, _directory: Path) -> None:
            self.calls = 0
            self.prompts: list[str] = []

        def install_signal_handlers(self) -> None:
            return None

        def restore_signal_handlers(self) -> None:
            return None

        def run_iteration(self, state: RalphState) -> IterationResult:
            self.calls += 1
            self.prompts.append(state.prompt)
            return IterationResult(0, f"iteration {self.calls}\n")

    monkeypatch.setattr("ralph.commands.ensure_runtime_dependencies", lambda: None)
    supervisor = FakeSupervisor(tmp_path)
    monkeypatch.setattr("ralph.commands.LoopSupervisor", lambda _directory: supervisor)
    monkeypatch.setattr("ralph.commands.is_ralph_process", lambda _pid: False)

    exit_code = start_command(make_start_args(max_iterations=2), tmp_path)
    state = load_state(tmp_path)
    captured = capsys.readouterr()

    assert exit_code == 0
    assert state is not None
    assert state.status == "max_iterations_reached"
    assert state.iteration == 2
    assert "Ralph loop stopped after 2 iterations." in captured.out


def test_start_command_sleeps_between_iterations(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    class FakeSupervisor:
        def __init__(self, _directory: Path) -> None:
            self.calls = 0
            self.prompts: list[str] = []

        def install_signal_handlers(self) -> None:
            return None

        def restore_signal_handlers(self) -> None:
            return None

        def run_iteration(self, state: RalphState) -> IterationResult:
            self.calls += 1
            self.prompts.append(state.prompt)
            return IterationResult(0, f"iteration {self.calls}\n")

    sleeps: list[int] = []
    monkeypatch.setattr("ralph.commands.ensure_runtime_dependencies", lambda: None)
    supervisor = FakeSupervisor(tmp_path)
    monkeypatch.setattr("ralph.commands.LoopSupervisor", lambda _directory: supervisor)
    monkeypatch.setattr("ralph.commands.is_ralph_process", lambda _pid: False)
    monkeypatch.setattr(
        "ralph.commands.time.sleep", lambda seconds: sleeps.append(seconds)
    )

    exit_code = start_command(make_start_args(max_iterations=2, sleep=3), tmp_path)
    state = load_state(tmp_path)

    assert exit_code == 0
    assert state is not None
    assert state.sleep_seconds == 3
    assert sleeps == [3]
    assert "<promise>COMPLETE</promise>" in supervisor.prompts[0]
    assert supervisor.prompts[0].endswith("The task is:\nBuild docs")


def test_start_command_can_disable_standard_prompt(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    class FakeSupervisor:
        def __init__(self, _directory: Path) -> None:
            self.prompts: list[str] = []

        def install_signal_handlers(self) -> None:
            return None

        def restore_signal_handlers(self) -> None:
            return None

        def run_iteration(self, state: RalphState) -> IterationResult:
            self.prompts.append(state.prompt)
            return IterationResult(0, "<promise>COMPLETE</promise>\n")

    monkeypatch.setattr("ralph.commands.ensure_runtime_dependencies", lambda: None)
    supervisor = FakeSupervisor(tmp_path)
    monkeypatch.setattr("ralph.commands.LoopSupervisor", lambda _directory: supervisor)
    monkeypatch.setattr("ralph.commands.is_ralph_process", lambda _pid: False)

    exit_code = start_command(make_start_args(no_standard_prompt=True), tmp_path)
    state = load_state(tmp_path)

    assert exit_code == 0
    assert state is not None
    assert state.inject_standard_prompt is False
    assert supervisor.prompts == ["Build docs"]


def test_start_command_uses_custom_state_file(
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

        def run_iteration(self, _state: RalphState) -> IterationResult:
            return IterationResult(0, "<promise>COMPLETE</promise>\n")

    monkeypatch.setattr("ralph.commands.ensure_runtime_dependencies", lambda: None)
    monkeypatch.setattr("ralph.commands.LoopSupervisor", FakeSupervisor)
    monkeypatch.setattr("ralph.commands.is_ralph_process", lambda _pid: False)

    exit_code = start_command(make_start_args(state_file="custom-state.md"), tmp_path)
    state = load_state(tmp_path, "custom-state.md")
    default_state = load_state(tmp_path)

    assert exit_code == 0
    assert state is not None
    assert default_state is None


def test_start_command_reports_iteration_failure(
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

        def run_iteration(self, _state: RalphState) -> IterationResult:
            return IterationResult(23, "forced failure")

    monkeypatch.setattr("ralph.commands.ensure_runtime_dependencies", lambda: None)
    monkeypatch.setattr("ralph.commands.LoopSupervisor", FakeSupervisor)
    monkeypatch.setattr("ralph.commands.is_ralph_process", lambda _pid: False)

    exit_code = start_command(make_start_args(), tmp_path)
    state = load_state(tmp_path)
    captured = capsys.readouterr()

    assert exit_code == 23
    assert state is not None
    assert state.status == "failed"
    assert "opencode exited with code 23" in captured.err


def test_start_command_treats_sigint_exit_as_cancelled(
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

        def run_iteration(self, _state: RalphState) -> IterationResult:
            return IterationResult(130, "hello\n")

    monkeypatch.setattr("ralph.commands.ensure_runtime_dependencies", lambda: None)
    monkeypatch.setattr("ralph.commands.LoopSupervisor", FakeSupervisor)
    monkeypatch.setattr("ralph.commands.is_ralph_process", lambda _pid: False)

    exit_code = start_command(make_start_args(), tmp_path)
    state = load_state(tmp_path)
    captured = capsys.readouterr()

    assert exit_code == 130
    assert state is not None
    assert state.status == "cancelled"
    assert captured.err == ""


def test_start_command_marks_cancelled_on_signal(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    class FakeSupervisor:
        def __init__(self, _directory: Path) -> None:
            return None

        def install_signal_handlers(self) -> None:
            return None

        def restore_signal_handlers(self) -> None:
            return None

        def run_iteration(self, _state: RalphState) -> IterationResult:
            raise LoopInterrupted(15)

    monkeypatch.setattr("ralph.commands.ensure_runtime_dependencies", lambda: None)
    monkeypatch.setattr("ralph.commands.LoopSupervisor", FakeSupervisor)
    monkeypatch.setattr("ralph.commands.is_ralph_process", lambda _pid: False)

    exit_code = start_command(make_start_args(), tmp_path)
    state = load_state(tmp_path)

    assert exit_code == 143
    assert state is not None
    assert state.status == "cancelled"
    assert state.last_exit_code == 143


def test_start_command_rejects_active_existing_loop(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    save_state(
        tmp_path,
        RalphState(
            active=True,
            status="running",
            iteration=1,
            agent="vibe",
            model="model",
            pid=99,
        ),
    )
    monkeypatch.setattr("ralph.commands.ensure_runtime_dependencies", lambda: None)
    monkeypatch.setattr("ralph.commands.is_ralph_process", lambda _pid: True)

    with pytest.raises(CommandError, match="an active Ralph loop is already running"):
        start_command(make_start_args(), tmp_path)


def test_status_command_reports_missing_state(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    exit_code = status_command(argparse.Namespace(), tmp_path)

    captured = capsys.readouterr()

    assert exit_code == 1
    assert "No Ralph loop state found." in captured.out


def test_status_command_reports_running_process(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    save_state(
        tmp_path,
        RalphState(
            active=True,
            status="running",
            iteration=2,
            max_iterations=5,
            completion_promise="DONE",
            timeout_seconds=45,
            started_at="2026-05-20T00:00:00Z",
            updated_at="2026-05-20T00:01:00Z",
            agent="vibe",
            model="model",
            pid=123,
            prompt="Wait here",
        ),
    )
    monkeypatch.setattr("ralph.commands.is_ralph_process", lambda _pid: True)

    exit_code = status_command(argparse.Namespace(), tmp_path)
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Status: running" in captured.out
    assert "Process: running" in captured.out
    assert "Iteration timeout: 45s" in captured.out
    assert "Sleep between iterations: 0s" in captured.out
    assert "Standard prompt injection: enabled" in captured.out


def test_status_command_uses_custom_state_file(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    save_state(
        tmp_path,
        RalphState(status="running", prompt="Prompt"),
        "custom-state.md",
    )
    monkeypatch.setattr("ralph.commands.is_ralph_process", lambda _pid: False)

    exit_code = status_command(
        argparse.Namespace(state_file="custom-state.md"), tmp_path
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "State file:" in captured.out
    assert "custom-state.md" in captured.out
