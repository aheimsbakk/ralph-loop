from __future__ import annotations

import codecs
import logging
import os
import select
import shutil
import sys
import threading
import time
from pathlib import Path
from typing import Any

from .constants import MAX_OUTPUT_BYTES
from .models import IterationResult, RalphLoopOptions
from .process_runner import ProcessRunner, OutputReader
from .signal_handler import SignalHandler

logger = logging.getLogger(__name__)


class CommandError(Exception):
    def __init__(self, message: str, exit_code: int = 1) -> None:
        super().__init__(message)
        self.message = message
        self.exit_code = exit_code


class LoopInterrupted(Exception):
    def __init__(self, signum: int) -> None:
        super().__init__(signum)
        self.signum = signum


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
    if signum == 2:  # SIGINT
        return 130
    if signum == 15:  # SIGTERM
        return 143
    return 1


def normalize_whitespace(value: str) -> str:
    return " ".join(value.split())


def strip_terminal_control_sequences(value: str) -> str:
    import re

    ansi_pattern = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
    without_ansi = ansi_pattern.sub("", value)
    return without_ansi.replace("\r", "")


def promise_detected(text: str, expected: str | None) -> bool:
    import re

    if not expected:
        return False

    cleaned_text = strip_terminal_control_sequences(text)
    lines = [line.strip() for line in cleaned_text.splitlines() if line.strip()]
    if not lines:
        return False

    promise_pattern = re.compile(r"<promise>(.*?)</promise>", re.DOTALL)
    match = promise_pattern.fullmatch(lines[-1])
    if not match:
        return False

    return normalize_whitespace(match.group(1)) == normalize_whitespace(expected)


class LoopSupervisor:
    """Orchestrates ProcessRunner, OutputStreamer, and SignalHandler in the main loop."""

    def __init__(self, directory: Path) -> None:
        self._process_runner = ProcessRunner(directory)
        self._signal_handler = SignalHandler()

    @property
    def current_process(self) -> Any:
        return self._process_runner.process

    @current_process.setter
    def current_process(self, value: Any) -> None:
        self._process_runner.process = value

    @property
    def current_output_fd(self) -> int | None:
        return self._process_runner.master_fd

    @current_output_fd.setter
    def current_output_fd(self, value: int | None) -> None:
        self._process_runner.master_fd = value

    @property
    def current_slave_fd(self) -> int | None:
        return self._process_runner.slave_fd

    @current_slave_fd.setter
    def current_slave_fd(self, value: int | None) -> None:
        self._process_runner.slave_fd = value

    def install_signal_handlers(self) -> None:
        self._signal_handler.install()

    def restore_signal_handlers(self) -> None:
        self._signal_handler.restore()

    def run_iteration(
        self, options: RalphLoopOptions, iteration: int
    ) -> IterationResult:
        suffix = f"/{options.max_iterations}" if options.max_iterations else ""
        print(f"=== ralph-loop iteration {iteration}{suffix} ===")

        stdin_thread: threading.Thread | None = None
        if not sys.stdin.isatty():
            stdin_thread = threading.Thread(
                target=self._forward_stdin,
                args=(self._process_runner,),
                daemon=True,
            )

        self._process_runner.start(options.wrapped_command, stdin_thread)

        # Wire stop callback for signal handler
        output_parts: list[str] = []
        decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")

        def stop_process() -> str:
            return self._process_runner.stop(output_parts, decoder)

        self._signal_handler.set_stop_callback(stop_process)

        stdout_fd = self._process_runner.master_fd
        assert stdout_fd is not None
        deadline = time.monotonic() + options.timeout_seconds

        try:
            while True:
                if time.monotonic() >= deadline:
                    output = stop_process()
                    return IterationResult(exit_code=124, output=output)

                if self._signal_handler.interrupted.is_set():
                    signum = self._signal_handler.signum
                    assert signum is not None
                    raise LoopInterrupted(signum)

                ready, _, _ = select.select([stdout_fd], [], [], 0.1)
                if self._signal_handler.interrupted.is_set():
                    signum = self._signal_handler.signum
                    assert signum is not None
                    raise LoopInterrupted(signum)

                if ready:
                    output_reader = OutputReader(output_parts, decoder)
                    if not output_reader.read(stdout_fd):
                        break

                process = self._process_runner.process
                if process is not None and process.poll() is not None and not ready:
                    output_reader = OutputReader(output_parts, decoder)
                    if not output_reader.read(stdout_fd):
                        break

                if self._signal_handler.interrupted.is_set():
                    signum = self._signal_handler.signum
                    assert signum is not None
                    raise LoopInterrupted(signum)
        finally:
            if stdin_thread is not None:
                stdin_thread.join()
            self._process_runner.cleanup()

        self._truncate_output_parts(output_parts)
        output = OutputReader(output_parts, decoder).finalize()
        process = self._process_runner.process
        return IterationResult(
            exit_code=(process.returncode if process is not None else 0) or 0,
            output=output,
        )

    def _forward_stdin(self, runner: ProcessRunner) -> None:
        while True:
            chunk = sys.stdin.buffer.read(4096)
            if not chunk:
                break
            try:
                if runner.process is not None and runner.process.stdin is not None:
                    runner.process.stdin.write(chunk)
            except (BrokenPipeError, OSError):
                break
        try:
            if runner.process is not None and runner.process.stdin is not None:
                runner.process.stdin.close()
        except OSError:
            pass

    def _truncate_output_parts(self, output_parts: list[str]) -> None:
        total_bytes = sum(len(part.encode("utf-8")) for part in output_parts)
        if total_bytes <= MAX_OUTPUT_BYTES:
            return
        start = 0
        while start < len(output_parts):
            if total_bytes <= MAX_OUTPUT_BYTES:
                break
            removed = len(output_parts[start].encode("utf-8"))
            total_bytes -= removed
            start += 1
        del output_parts[:start]
