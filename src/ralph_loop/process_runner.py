from __future__ import annotations

import codecs
import errno
import logging
import os
from pathlib import Path
import pty
import select
import subprocess
import threading
import time

from .constants import TERMINATION_GRACE_SECONDS

logger = logging.getLogger(__name__)


class ProcessRunner:
    """Manages subprocess creation, PTY file descriptors, and process lifecycle."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.process: subprocess.Popen[bytes] | None = None
        self.master_fd: int | None = None
        self.slave_fd: int | None = None

    def start(
        self,
        command: tuple[str, ...],
        stdin_forwarder: threading.Thread | None = None,
    ) -> tuple[subprocess.Popen[bytes], int, int]:
        master_fd, slave_fd = pty.openpty()
        stdin_target = slave_fd if stdin_forwarder is None else subprocess.PIPE
        process = subprocess.Popen(
            list(command),
            cwd=self.directory,
            stdin=stdin_target,
            stdout=slave_fd,
            stderr=slave_fd,
        )
        self.process = process
        self.master_fd = master_fd
        self.slave_fd = slave_fd
        self._close_fd(slave_fd)

        if stdin_forwarder is not None:
            stdin_forwarder.start()

        return process, master_fd, slave_fd

    def stop(
        self, output_parts: list[str], decoder: codecs.IncrementalDecoder | None
    ) -> str:
        process = self.process
        if process is None:
            return ""

        stdout_fd = self.master_fd

        if process.poll() is None:
            if self.slave_fd is not None:
                self._close_fd(self.slave_fd)
                self.slave_fd = None
            if process.stdin is not None:
                try:
                    process.stdin.close()
                except OSError:
                    pass
            process.terminate()

        output = self._wait_for_termination(process, stdout_fd, output_parts, decoder)
        return output

    def _wait_for_termination(
        self,
        process: subprocess.Popen[bytes],
        stdout_fd: int | None,
        output_parts: list[str],
        decoder: codecs.IncrementalDecoder | None,
    ) -> str:
        output_reader = OutputReader(output_parts, decoder)
        deadline = time.monotonic() + TERMINATION_GRACE_SECONDS

        while True:
            if stdout_fd is not None:
                ready, _, _ = select.select([stdout_fd], [], [], 0.1)
                if ready:
                    if not output_reader.read(stdout_fd):
                        break

            if process.poll() is not None:
                break

            if time.monotonic() >= deadline:
                process.kill()
                deadline = float("inf")

        if stdout_fd is not None:
            while output_reader.read(stdout_fd):
                continue

        return output_reader.finalize()

    def cleanup(self) -> None:
        if self.master_fd is not None:
            self._close_fd(self.master_fd)
            self.master_fd = None
        self.process = None
        self.slave_fd = None

    def _close_fd(self, file_descriptor: int) -> None:
        try:
            os.close(file_descriptor)
        except OSError:
            pass


class OutputReader:
    """Reads from a PTY master fd, decodes UTF-8, prints to terminal, appends to buffer."""

    def __init__(
        self,
        output_parts: list[str],
        decoder: codecs.IncrementalDecoder | None,
    ) -> None:
        self._output_parts = output_parts
        self._decoder = decoder

    def read(self, fd: int, process: subprocess.Popen[bytes] | None = None) -> bool:
        try:
            chunk = os.read(fd, 4096)
        except OSError as error:
            if error.errno in (errno.EBADF, errno.EIO):
                return False
            raise

        if not chunk:
            return False

        text = (
            chunk.decode("utf-8", errors="replace")
            if self._decoder is None
            else self._decoder.decode(chunk)
        )
        if text:
            print(text, end="", flush=True)
            self._output_parts.append(text)
        return True

    def finalize(self) -> str:
        if self._decoder is not None:
            tail = self._decoder.decode(b"", final=True)
            if tail:
                print(tail, end="", flush=True)
                self._output_parts.append(tail)
        return "".join(self._output_parts)
