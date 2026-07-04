from __future__ import annotations

import errno
import os
from pathlib import Path
import signal
import subprocess
from typing import Any

import pytest

from ralph_loop.models import RalphLoopOptions
from ralph_loop.constants import MAX_OUTPUT_BYTES
from ralph_loop.runtime import LoopInterrupted, LoopSupervisor
from ralph_loop.utils import (
    CommandError,
    ensure_command_available,
    normalize_whitespace,
    promise_detected,
    signal_exit_code,
    strip_terminal_control_sequences,
)
from ralph_loop.process_runner import ProcessRunner, OutputReader
from ralph_loop.signal_handler import SignalHandler


class FakeProcess:
    def __init__(
        self,
        *,
        output: str = "",
        returncode: int | None = 0,
        timeout: bool = False,
        pid: int | None = None,
    ) -> None:
        self.output = output
        self.returncode = returncode
        self.timeout = timeout
        self.terminated = False
        self.killed = False
        self.pid = pid
        self.stdin: Any = None

    def communicate(self, timeout: int | None = None) -> tuple[str, None]:
        if self.timeout:
            self.timeout = False
            raise subprocess.TimeoutExpired(cmd=["opencode"], timeout=timeout or 0)
        return self.output, None

    def poll(self) -> int | None:
        if self.returncode is None:
            return None
        return None if not (self.terminated or self.killed) else self.returncode

    def terminate(self) -> None:
        self.terminated = True

    def kill(self) -> None:
        self.killed = True


def test_ensure_command_available_requires_command_on_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("ralph_loop.utils.shutil.which", lambda _name: None)  # pyright: ignore[reportUnknownArgumentType, reportUnknownLambdaType]

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

    monkeypatch.setattr("sys.stdin.isatty", lambda: True)  # pyright: ignore[reportUnknownArgumentType, reportUnknownLambdaType]
    monkeypatch.setattr("ralph_loop.process_runner.subprocess.Popen", fake_popen)
    monkeypatch.setattr(
        "ralph_loop.process_runner.pty.openpty", lambda: (read_fd, write_fd)
    )  # pyright: ignore[reportUnknownLambdaType]
    monkeypatch.setattr(
        "ralph_loop.process_runner.select.select",
        lambda *args, **kwargs: ([read_fd], [], []),  # pyright: ignore[reportUnknownArgumentType, reportUnknownLambdaType]
    )

    supervisor = LoopSupervisor(tmp_path)
    result = supervisor.run_iteration(
        RalphLoopOptions(
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
    assert popen_kwargs["stdin"] == write_fd
    assert popen_kwargs["stdout"] == write_fd
    assert popen_kwargs["stderr"] == write_fd
    assert "=== ralph-loop iteration 2/5 ===" in captured.out
    assert "done\n" in captured.out


def test_loop_supervisor_returns_timeout_code(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)  # pyright: ignore[reportUnknownArgumentType, reportUnknownLambdaType]
    read_fd, write_fd = os.pipe()
    os.write(write_fd, b"slow\n")
    os.close(write_fd)
    fake_process = FakeProcess(output="", returncode=0)
    monkeypatch.setattr(
        "ralph_loop.process_runner.subprocess.Popen",
        lambda *args, **kwargs: fake_process,  # pyright: ignore[reportUnknownArgumentType, reportUnknownLambdaType]
    )
    monkeypatch.setattr(
        "ralph_loop.process_runner.pty.openpty", lambda: (read_fd, write_fd)
    )  # pyright: ignore[reportUnknownLambdaType]
    steps = iter([0.0, 2.0, 2.0, 3.0])
    monkeypatch.setattr("ralph_loop.process_runner.time.monotonic", lambda: next(steps))  # pyright: ignore[reportUnknownLambdaType]
    monkeypatch.setattr(
        "ralph_loop.process_runner.select.select",
        lambda *args, **kwargs: ([read_fd], [], []),  # pyright: ignore[reportUnknownArgumentType, reportUnknownLambdaType]
    )

    supervisor = LoopSupervisor(tmp_path)
    result = supervisor.run_iteration(
        RalphLoopOptions(
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


def test_loop_supervisor_timeout_closes_slave_fd(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)  # pyright: ignore[reportUnknownArgumentType, reportUnknownLambdaType]
    read_fd, write_fd = os.pipe()
    os.write(write_fd, b"slow\n")
    os.close(write_fd)
    fake_process = FakeProcess(output="", returncode=0)
    monkeypatch.setattr(
        "ralph_loop.process_runner.subprocess.Popen",
        lambda *args, **kwargs: fake_process,  # pyright: ignore[reportUnknownArgumentType, reportUnknownLambdaType]
    )
    monkeypatch.setattr(
        "ralph_loop.process_runner.pty.openpty", lambda: (read_fd, write_fd)
    )  # pyright: ignore[reportUnknownLambdaType]
    steps = iter([0.0, 2.0, 2.0, 3.0])
    monkeypatch.setattr("ralph_loop.process_runner.time.monotonic", lambda: next(steps))  # pyright: ignore[reportUnknownLambdaType]
    monkeypatch.setattr(
        "ralph_loop.process_runner.select.select",
        lambda *args, **kwargs: ([read_fd], [], []),  # pyright: ignore[reportUnknownArgumentType, reportUnknownLambdaType]
    )

    close_calls: list[int] = []
    original_os_close = os.close

    def track_close(fd: int) -> None:
        close_calls.append(fd)
        original_os_close(fd)

    monkeypatch.setattr("ralph_loop.process_runner.os.close", track_close)

    supervisor = LoopSupervisor(tmp_path)
    supervisor.run_iteration(
        RalphLoopOptions(
            wrapped_command=("opencode", "run", "Prompt"),
            timeout_seconds=1,
        ),
        1,
    )

    assert fake_process.terminated is True
    assert write_fd in close_calls
    terminate_index = close_calls.index(write_fd)
    assert terminate_index == 0, (
        f"slave fd {write_fd} should be closed before terminate(), "
        f"but close calls were: {close_calls}"
    )


def test_output_buffer_truncated_at_max_bytes() -> None:
    parts: list[str] = []
    part_size = MAX_OUTPUT_BYTES // 2 + 1
    parts.append("a" * part_size)
    parts.append("b" * part_size)
    parts.append("c" * part_size)

    output_reader = OutputReader(parts, None)
    output_reader.truncate(MAX_OUTPUT_BYTES)

    total_bytes = sum(len(part.encode("utf-8")) for part in parts)
    assert total_bytes <= MAX_OUTPUT_BYTES
    assert parts == ["c" * part_size]


def test_output_buffer_not_truncated_when_under_limit() -> None:
    parts = ["x" * 100, "y" * 100]

    output_reader = OutputReader(parts, None)
    output_reader.truncate(MAX_OUTPUT_BYTES)

    assert parts == ["x" * 100, "y" * 100]


def test_promise_detected_after_truncation_still_works() -> None:
    small = "a" * 50 + "\n"
    promise_line = "<promise>DONE</promise>\n"
    parts = [small, promise_line]

    output_reader = OutputReader(parts, None)
    output_reader.truncate(MAX_OUTPUT_BYTES)

    combined = "".join(parts)
    assert promise_detected(combined, "DONE") is True


def test_signal_handler_sets_event_not_raises(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    read_fd, write_fd = os.pipe()
    os.write(write_fd, b"output\n")
    os.close(write_fd)
    fake_process = FakeProcess(output="", returncode=0)

    runner = ProcessRunner(tmp_path)
    runner.process = fake_process
    runner.master_fd = read_fd
    runner.slave_fd = write_fd

    handler = SignalHandler()

    def stop_callback() -> str:
        return runner.stop([], None)

    handler.set_stop_callback(stop_callback)
    handler.install()

    handler._handle_signal(signal.SIGINT, None)

    assert handler.interrupted.is_set()
    assert handler.signum == signal.SIGINT
    assert fake_process.terminated is True

    handler.restore()


def test_loop_interrupted_raised_in_main_thread(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)  # pyright: ignore[reportUnknownArgumentType, reportUnknownLambdaType]
    read_fd, write_fd = os.pipe()
    os.write(write_fd, b"output\n")
    os.close(write_fd)
    fake_process = FakeProcess(output="", returncode=0)

    def fake_popen(*args: object, **kwargs: object) -> FakeProcess:
        return fake_process

    monkeypatch.setattr("ralph_loop.process_runner.subprocess.Popen", fake_popen)  # pyright: ignore[reportUnknownArgumentType, reportUnknownLambdaType]
    monkeypatch.setattr(
        "ralph_loop.process_runner.pty.openpty", lambda: (read_fd, write_fd)
    )  # pyright: ignore[reportUnknownLambdaType]
    call_count = 0

    def fake_select(
        *args: object, **kwargs: object
    ) -> tuple[list[int], list[int], list[int]]:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return ([read_fd], [], [])
        return ([], [], [])

    monkeypatch.setattr("ralph_loop.process_runner.select.select", fake_select)  # pyright: ignore[reportUnknownArgumentType, reportUnknownLambdaType]

    supervisor = LoopSupervisor(tmp_path)
    supervisor.install_signal_handlers()

    supervisor._signal_handler._handle_signal(signal.SIGINT, None)

    with pytest.raises(LoopInterrupted) as exc_info:
        supervisor.run_iteration(
            RalphLoopOptions(
                wrapped_command=("opencode", "run", "Prompt"),
                max_iterations=5,
            ),
            1,
        )

    assert exc_info.value.signum == signal.SIGINT

    supervisor.restore_signal_handlers()


def test_read_unexpected_ebadf_warns(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, tmp_path: Path
) -> None:
    read_fd, write_fd = os.pipe()
    os.close(write_fd)
    fake_process = FakeProcess(output="", returncode=None)

    runner = ProcessRunner(tmp_path)
    runner.process = fake_process
    runner.master_fd = read_fd
    runner.slave_fd = None

    def fake_os_read(fd: int, size: int) -> bytes:
        raise OSError(errno.EBADF, os.strerror(errno.EBADF))

    monkeypatch.setattr("ralph_loop.process_runner.os.read", fake_os_read)

    output_reader = OutputReader([], None)
    result = output_reader.read(read_fd)

    assert result is False


def test_read_expected_ebadf_returns_false(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, tmp_path: Path
) -> None:
    read_fd, write_fd = os.pipe()
    os.close(write_fd)
    fake_process = FakeProcess(output="", returncode=0)
    fake_process.terminated = True

    runner = ProcessRunner(tmp_path)
    runner.process = fake_process
    runner.master_fd = read_fd
    runner.slave_fd = None

    def fake_os_read(fd: int, size: int) -> bytes:
        raise OSError(errno.EBADF, os.strerror(errno.EBADF))

    monkeypatch.setattr("ralph_loop.process_runner.os.read", fake_os_read)

    output_reader = OutputReader([], None)
    result = output_reader.read(read_fd)

    assert result is False


def test_loop_supervisor_forwards_piped_stdin(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    read_fd, write_fd = os.pipe()
    os.write(write_fd, b"output\n")
    os.close(write_fd)
    fake_process = FakeProcess(output="", returncode=0)

    stdin_data: list[bytes] = []

    def fake_popen(command: list[str], *args: object, **kwargs: object) -> FakeProcess:
        fake_process.stdin = fake_process
        fake_process.stdin.write = lambda data: stdin_data.append(data)
        fake_process.stdin.close = lambda: None
        return fake_process

    monkeypatch.setattr("ralph_loop.process_runner.subprocess.Popen", fake_popen)
    monkeypatch.setattr(
        "ralph_loop.process_runner.pty.openpty", lambda: (read_fd, write_fd)
    )  # pyright: ignore[reportUnknownLambdaType]
    monkeypatch.setattr(
        "ralph_loop.process_runner.select.select",
        lambda *args, **kwargs: ([read_fd], [], []),  # pyright: ignore[reportUnknownArgumentType, reportUnknownLambdaType]
    )

    stdin_read = iter([b"hello ", b"world", b""])

    def fake_stdin_read(size: int) -> bytes:
        result = next(stdin_read)
        return result

    monkeypatch.setattr("sys.stdin.isatty", lambda: False)  # pyright: ignore[reportUnknownArgumentType, reportUnknownLambdaType]
    monkeypatch.setattr("sys.stdin.buffer.read", fake_stdin_read)  # pyright: ignore[reportUnknownArgumentType, reportUnknownLambdaType]

    supervisor = LoopSupervisor(tmp_path)
    supervisor.run_iteration(
        RalphLoopOptions(
            wrapped_command=("opencode", "run", "Prompt"),
            max_iterations=5,
        ),
        1,
    )

    assert b"".join(stdin_data) == b"hello world"


def test_loop_supervisor_stdin_eof_stops_writer(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    read_fd, write_fd = os.pipe()
    os.write(write_fd, b"output\n")
    os.close(write_fd)
    fake_process = FakeProcess(output="", returncode=0)

    stdin_data: list[bytes] = []
    close_called = [False]

    def fake_popen(command: list[str], *args: object, **kwargs: object) -> FakeProcess:
        fake_process.stdin = fake_process
        fake_process.stdin.write = lambda data: stdin_data.append(data)
        fake_process.stdin.close = lambda: close_called.__setitem__(0, True)
        return fake_process

    monkeypatch.setattr("ralph_loop.process_runner.subprocess.Popen", fake_popen)
    monkeypatch.setattr(
        "ralph_loop.process_runner.pty.openpty", lambda: (read_fd, write_fd)
    )  # pyright: ignore[reportUnknownLambdaType]
    monkeypatch.setattr(
        "ralph_loop.process_runner.select.select",
        lambda *args, **kwargs: ([read_fd], [], []),  # pyright: ignore[reportUnknownArgumentType, reportUnknownLambdaType]
    )

    stdin_read = iter([b"some data", b""])

    def fake_stdin_read(size: int) -> bytes:
        result = next(stdin_read)
        return result

    monkeypatch.setattr("sys.stdin.isatty", lambda: False)  # pyright: ignore[reportUnknownArgumentType, reportUnknownLambdaType]
    monkeypatch.setattr("sys.stdin.buffer.read", fake_stdin_read)  # pyright: ignore[reportUnknownArgumentType, reportUnknownLambdaType]

    supervisor = LoopSupervisor(tmp_path)
    supervisor.run_iteration(
        RalphLoopOptions(
            wrapped_command=("opencode", "run", "Prompt"),
            max_iterations=5,
        ),
        1,
    )

    assert b"".join(stdin_data) == b"some data"
    assert close_called[0] is True


def test_loop_supervisor_no_stdin_pipe_when_terminal(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    read_fd, write_fd = os.pipe()
    os.write(write_fd, b"output\n")
    os.close(write_fd)
    fake_process = FakeProcess(output="", returncode=0)
    popen_kwargs: dict[str, object] = {}

    def fake_popen(command: list[str], *args: object, **kwargs: object) -> FakeProcess:
        popen_kwargs.update(kwargs)
        return fake_process

    monkeypatch.setattr("ralph_loop.process_runner.subprocess.Popen", fake_popen)
    monkeypatch.setattr(
        "ralph_loop.process_runner.pty.openpty", lambda: (read_fd, write_fd)
    )  # pyright: ignore[reportUnknownLambdaType]
    monkeypatch.setattr(
        "ralph_loop.process_runner.select.select",
        lambda *args, **kwargs: ([read_fd], [], []),  # pyright: ignore[reportUnknownArgumentType, reportUnknownLambdaType]
    )

    monkeypatch.setattr("sys.stdin.isatty", lambda: True)  # pyright: ignore[reportUnknownArgumentType, reportUnknownLambdaType]

    supervisor = LoopSupervisor(tmp_path)
    supervisor.run_iteration(
        RalphLoopOptions(
            wrapped_command=("opencode", "run", "Prompt"),
            max_iterations=5,
        ),
        1,
    )

    assert popen_kwargs["stdin"] == write_fd
