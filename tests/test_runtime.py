from __future__ import annotations

import os
from pathlib import Path
import signal
import subprocess

import pytest

from ralph.models import RalphState
from ralph.runtime import (
    CommandError,
    LoopSupervisor,
    ensure_runtime_dependencies,
    is_ralph_process,
    signal_exit_code,
)


class FakeProcess:
    def __init__(
        self, *, output: str = "", returncode: int = 0, timeout: bool = False
    ) -> None:
        self.output = output
        self.returncode = returncode
        self.timeout = timeout
        self.terminated = False
        self.killed = False

    def communicate(self, timeout: int | None = None) -> tuple[str, None]:
        if self.timeout:
            self.timeout = False
            raise subprocess.TimeoutExpired(cmd=["opencode"], timeout=timeout or 0)
        return self.output, None

    def poll(self) -> int | None:
        return None if not (self.terminated or self.killed) else self.returncode

    def terminate(self) -> None:
        self.terminated = True

    def kill(self) -> None:
        self.killed = True


def test_ensure_runtime_dependencies_requires_opencode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("ralph.runtime.shutil.which", lambda _name: None)

    with pytest.raises(CommandError, match="opencode is required"):
        ensure_runtime_dependencies()


def test_signal_exit_code_maps_expected_values() -> None:
    assert signal_exit_code(signal.SIGINT) == 130
    assert signal_exit_code(signal.SIGTERM) == 143


def test_is_ralph_process_returns_false_for_missing_process(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_kill(_pid: int, _sig: int) -> None:
        raise OSError("missing")

    monkeypatch.setattr("ralph.runtime.os.kill", fake_kill)

    assert is_ralph_process(99) is False


def test_loop_supervisor_runs_iteration(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    captured_command: list[str] = []
    popen_kwargs: dict[str, object] = {}
    read_fd, write_fd = os.pipe()
    os.write(write_fd, b"done\n")
    os.close(write_fd)
    fake_process = FakeProcess(output="", returncode=0)

    def fake_popen(command: list[str], *args: object, **kwargs: object) -> FakeProcess:
        captured_command.extend(command)
        popen_kwargs.update(kwargs)
        return fake_process

    monkeypatch.setattr("ralph.runtime.subprocess.Popen", fake_popen)
    monkeypatch.setattr("ralph.runtime.pty.openpty", lambda: (read_fd, write_fd))
    monkeypatch.setattr(
        "ralph.runtime.select.select", lambda *args, **kwargs: ([read_fd], [], [])
    )

    supervisor = LoopSupervisor(tmp_path)
    result = supervisor.run_iteration(
        RalphState(
            iteration=2,
            max_iterations=5,
            agent="vibe",
            model="m",
            opencode_args=("--print-logs", "--session", "session-123"),
            prompt="Prompt",
        )
    )
    captured = capsys.readouterr()

    assert result.exit_code == 0
    assert result.output == "done\n"
    assert captured_command[:5] == [
        "opencode",
        "--print-logs",
        "--session",
        "session-123",
        "run",
    ]
    assert popen_kwargs["stdin"] is subprocess.DEVNULL
    assert popen_kwargs["stdout"] == write_fd
    assert popen_kwargs["stderr"] == write_fd
    assert "=== Ralph iteration 2/5 ===" in captured.out
    assert "done\n" in captured.out


def test_loop_supervisor_returns_timeout_code(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    read_fd, write_fd = os.pipe()
    os.write(write_fd, b"slow\n")
    os.close(write_fd)
    fake_process = FakeProcess(output="", returncode=0)
    monkeypatch.setattr(
        "ralph.runtime.subprocess.Popen", lambda *args, **kwargs: fake_process
    )
    monkeypatch.setattr("ralph.runtime.pty.openpty", lambda: (read_fd, write_fd))
    steps = iter([0.0, 2.0, 2.0, 3.0])
    monkeypatch.setattr("ralph.runtime.time.monotonic", lambda: next(steps))
    monkeypatch.setattr(
        "ralph.runtime.select.select", lambda *args, **kwargs: ([read_fd], [], [])
    )

    supervisor = LoopSupervisor(tmp_path)
    result = supervisor.run_iteration(
        RalphState(
            iteration=1, timeout_seconds=1, agent="vibe", model="m", prompt="Prompt"
        )
    )
    captured = capsys.readouterr()

    assert result.exit_code == 124
    assert result.output == "slow\n"
    assert fake_process.terminated is True
    assert "slow" in captured.out
