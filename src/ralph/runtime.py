from __future__ import annotations

import codecs
import errno
import os
from pathlib import Path
import pty
import select
import shutil
import signal
import subprocess
import time
from types import FrameType
from typing import Any, cast

from .constants import TERMINATION_GRACE_SECONDS
from .models import IterationResult, RalphState


class CommandError(Exception):
    def __init__(self, message: str, exit_code: int = 1) -> None:
        super().__init__(message)
        self.message = message
        self.exit_code = exit_code


class LoopInterrupted(Exception):
    def __init__(self, signum: int) -> None:
        super().__init__(signum)
        self.signum = signum


def ensure_runtime_dependencies() -> None:
    if shutil.which("opencode") is None:
        raise CommandError("opencode is required")


def signal_exit_code(signum: int) -> int:
    if signum == signal.SIGINT:
        return 130
    if signum == signal.SIGTERM:
        return 143
    return 1


def is_ralph_process(pid: int | None) -> bool:
    if pid is None or pid <= 0:
        return False

    try:
        os.kill(pid, 0)
    except OSError:
        return False

    args = _read_process_args(pid)
    if not args or "start" not in args:
        return False

    basenames = {Path(arg).name for arg in args if arg}
    if "ralph" in basenames or "ralph.sh" in basenames:
        return True

    for index, arg in enumerate(args[:-1]):
        if arg == "-m" and args[index + 1] == "ralph":
            return True

    return any("ralph" in arg for arg in args)


def _read_process_args(pid: int) -> list[str]:
    cmdline_path = Path("/proc") / str(pid) / "cmdline"
    try:
        raw = cmdline_path.read_bytes()
    except OSError:
        return []

    return [part for part in raw.decode("utf-8", errors="ignore").split("\x00") if part]


class LoopSupervisor:
    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.current_process: subprocess.Popen[bytes] | None = None
        self.current_output_fd: int | None = None
        self._previous_handlers: dict[int, Any] = {}

    def install_signal_handlers(self) -> None:
        for signum in (signal.SIGINT, signal.SIGTERM):
            self._previous_handlers[signum] = signal.getsignal(signum)
            signal.signal(signum, self._handle_signal)

    def restore_signal_handlers(self) -> None:
        for signum, handler in self._previous_handlers.items():
            signal.signal(signum, cast(Any, handler))
        self._previous_handlers.clear()

    def run_iteration(self, state: RalphState) -> IterationResult:
        suffix = f"/{state.max_iterations}" if state.max_iterations else ""
        print(f"=== Ralph iteration {state.iteration}{suffix} ===")

        master_fd, slave_fd = pty.openpty()
        process = subprocess.Popen(
            [
                "opencode",
                "run",
                "--agent",
                state.agent or "",
                "--model",
                state.model or "",
                state.prompt,
            ],
            cwd=self.directory,
            stdin=subprocess.DEVNULL,
            stdout=slave_fd,
            stderr=slave_fd,
        )
        self.current_process = process
        self.current_output_fd = master_fd
        self._close_fd(slave_fd)

        output_parts: list[str] = []
        decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        stdout_fd = master_fd
        deadline = time.monotonic() + state.timeout_seconds

        try:
            while True:
                if time.monotonic() >= deadline:
                    output = self._stop_current_process(output_parts, decoder)
                    return IterationResult(exit_code=124, output=output)

                ready, _, _ = select.select([stdout_fd], [], [], 0.1)
                if ready:
                    if not self._read_available_output(
                        stdout_fd, output_parts, decoder
                    ):
                        break

                if process.poll() is not None and not ready:
                    if not self._read_available_output(
                        stdout_fd, output_parts, decoder
                    ):
                        break
        finally:
            self.current_process = None
            self.current_output_fd = None
            self._close_fd(master_fd)
            self._close_fd(slave_fd)

        output = self._finalize_output(output_parts, decoder)
        return IterationResult(exit_code=process.returncode or 0, output=output)

    def _handle_signal(self, signum: int, _frame: FrameType | None) -> None:
        self._stop_current_process([], None)
        raise LoopInterrupted(signum)

    def _stop_current_process(
        self,
        output_parts: list[str],
        decoder: codecs.IncrementalDecoder | None,
    ) -> str:
        process = self.current_process
        if process is None:
            return ""

        stdout_fd = self.current_output_fd

        if process.poll() is None:
            process.terminate()

        deadline = time.monotonic() + TERMINATION_GRACE_SECONDS
        while True:
            if stdout_fd is not None:
                ready, _, _ = select.select([stdout_fd], [], [], 0.1)
                if ready:
                    if not self._read_available_output(
                        stdout_fd, output_parts, decoder
                    ):
                        break

            if process.poll() is not None:
                break

            if time.monotonic() >= deadline:
                process.kill()
                deadline = float("inf")

        if stdout_fd is not None:
            while self._read_available_output(stdout_fd, output_parts, decoder):
                continue

        return self._finalize_output(output_parts, decoder)

    def _read_available_output(
        self,
        stdout_fd: int,
        output_parts: list[str],
        decoder: codecs.IncrementalDecoder | None,
    ) -> bool:
        try:
            chunk = os.read(stdout_fd, 4096)
        except OSError as error:
            if error.errno in {errno.EBADF, errno.EIO}:
                return False
            raise

        if not chunk:
            return False

        text = (
            chunk.decode("utf-8", errors="replace")
            if decoder is None
            else decoder.decode(chunk)
        )
        if text:
            print(text, end="", flush=True)
            output_parts.append(text)
        return True

    def _finalize_output(
        self,
        output_parts: list[str],
        decoder: codecs.IncrementalDecoder | None,
    ) -> str:
        if decoder is not None:
            tail = decoder.decode(b"", final=True)
            if tail:
                print(tail, end="", flush=True)
                output_parts.append(tail)
        return "".join(output_parts)

    def _close_fd(self, file_descriptor: int) -> None:
        try:
            os.close(file_descriptor)
        except OSError:
            return
