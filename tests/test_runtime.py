from __future__ import annotations

import os
from pathlib import Path
import signal
import subprocess

import pytest

from ralph.models import RalphOptions
from ralph.runtime import (
    CommandError,
    LoopSupervisor,
    ensure_command_available,
    normalize_whitespace,
    promise_detected,
    signal_exit_code,
    strip_terminal_control_sequences,
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


def test_ensure_command_available_requires_command_on_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("ralph.runtime.shutil.which", lambda _name: None)

    with pytest.raises(CommandError, match="command not found: opencode"):
        ensure_command_available(("opencode",), Path("."))


def test_ensure_command_available_accepts_relative_executable(tmp_path: Path) -> None:
    script = tmp_path / "bin" / "runner"
    script.parent.mkdir()
    script.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    script.chmod(0o755)

    ensure_command_available(("bin/runner",), tmp_path)


def test_signal_exit_code_maps_expected_values() -> None:
    assert signal_exit_code(signal.SIGINT) == 130
    assert signal_exit_code(signal.SIGTERM) == 143


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
        RalphOptions(
            wrapped_command=("opencode", "run", "--model", "gpt-5", "Prompt"),
            max_iterations=5,
        ),
        2,
    )
    captured = capsys.readouterr()

    assert result.exit_code == 0
    assert result.output == "done\n"
    assert captured_command == [
        "opencode",
        "run",
        "--model",
        "gpt-5",
        "Prompt",
    ]
    assert popen_kwargs["stdin"] is None
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
        RalphOptions(
            wrapped_command=("opencode", "run", "Prompt"),
            timeout_seconds=1,
        ),
        1,
    )
    captured = capsys.readouterr()

    assert result.exit_code == 124
    assert result.output == "slow\n"
    assert fake_process.terminated is True
    assert "slow" in captured.out


def test_promise_detected_normalizes_whitespace() -> None:
    output = "before\n<promise>DONE   NOW</promise>\n"

    assert promise_detected(output, "DONE NOW") is True


def test_promise_detected_handles_missing_expected_value() -> None:
    assert promise_detected("<promise>DONE</promise>", None) is False


def test_promise_detected_ignores_non_final_promise_line() -> None:
    output = "I will only output <promise>DONE</promise> when truly complete.\nStill working.\n"

    assert promise_detected(output, "DONE") is False


def test_promise_detected_accepts_final_non_empty_promise_line() -> None:
    output = "Still working.\n<promise>DONE</promise>\n\n"

    assert promise_detected(output, "DONE") is True


def test_promise_detected_ignores_terminal_control_sequences() -> None:
    output = "\x1b[2K\r<promise>hello said</promise>\x1b[0m\r\n"

    assert promise_detected(output, "hello said") is True


def test_strip_terminal_control_sequences_removes_ansi_and_carriage_returns() -> None:
    assert (
        strip_terminal_control_sequences("\x1b[2K\r<promise>DONE</promise>\x1b[0m\r")
        == "<promise>DONE</promise>"
    )


def test_normalize_whitespace_collapses_runs() -> None:
    assert normalize_whitespace(" one\n\t two   three ") == "one two three"
