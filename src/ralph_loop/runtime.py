from __future__ import annotations

import codecs
import errno
import os
from pathlib import Path
import pty
import re
import select
import shutil
import signal
import subprocess
import time
from types import FrameType
from typing import Any, cast

from .constants import TERMINATION_GRACE_SECONDS
from .models import IterationResult, RalphLoopOptions


class CommandError(Exception):
    def __init__(self, message: str, exit_code: int = 1) -> None:
        super().__init__(message)
        self.message = message
        self.exit_code = exit_code


class LoopInterrupted(Exception):
    def __init__(self, signum: int) -> None:
        super().__init__(signum)
        self.signum = signum


PROMISE_PATTERN = re.compile(r"<promise>([\s\S]*?)</promise>")
ANSI_ESCAPE_PATTERN = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def ensure_command_available(command: tuple[str, ...], directory: Path) -> None:
    executable = command[0]
    if "/" in executable:
        path = Path(executable)
        if not path.is_absolute():
            path = directory / path
        if not path.exists():
            raise CommandError(f"command not found: {executable}")
        if not os.access(path, os.X_OK):
            raise CommandError(f"command is not executable: {executable}")
        return

    if shutil.which(executable) is None:
        raise CommandError(f"command not found: {executable}")


def signal_exit_code(signum: int) -> int:
    if signum == signal.SIGINT:
        return 130
    if signum == signal.SIGTERM:
        return 143
    return 1


def normalize_whitespace(value: str) -> str:
    return " ".join(value.split())


def strip_terminal_control_sequences(value: str) -> str:
    without_ansi = ANSI_ESCAPE_PATTERN.sub("", value)
    return without_ansi.replace("\r", "")


def promise_detected(text: str, expected: str | None) -> bool:
    if not expected:
        return False

    cleaned_text = strip_terminal_control_sequences(text)
    lines = [line.strip() for line in cleaned_text.splitlines() if line.strip()]
    if not lines:
        return False

    match = PROMISE_PATTERN.fullmatch(lines[-1])
    if not match:
        return False

    return normalize_whitespace(match.group(1)) == normalize_whitespace(expected)


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

    def run_iteration(
        self, options: RalphLoopOptions, iteration: int
    ) -> IterationResult:
        suffix = f"/{options.max_iterations}" if options.max_iterations else ""
        print(f"=== ralph-loop iteration {iteration}{suffix} ===")

        master_fd, slave_fd = pty.openpty()
        process = subprocess.Popen(
            [*options.wrapped_command],
            cwd=self.directory,
            stdin=None,
            stdout=slave_fd,
            stderr=slave_fd,
        )
        self.current_process = process
        self.current_output_fd = master_fd
        self._close_fd(slave_fd)

        output_parts: list[str] = []
        decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        stdout_fd = master_fd
        deadline = time.monotonic() + options.timeout_seconds

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
