from __future__ import annotations

import codecs
import logging
import select
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


class LoopInterrupted(Exception):
    def __init__(self, signum: int) -> None:
        super().__init__(signum)
        self.signum = signum


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
        output_reader = OutputReader(output_parts, decoder)

        def stop_process() -> str:
            return self._process_runner.stop(output_parts, decoder, output_reader)

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
                    if not output_reader.read(stdout_fd):
                        break

                process = self._process_runner.process
                if process is not None and process.poll() is not None and not ready:
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

        output_reader.truncate(MAX_OUTPUT_BYTES)
        output = output_reader.finalize()
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
