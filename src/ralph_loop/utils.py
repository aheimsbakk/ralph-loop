from __future__ import annotations

import os
import re
import shutil
from pathlib import Path


class CommandError(Exception):
    def __init__(self, message: str, exit_code: int = 1) -> None:
        super().__init__(message)
        self.message = message
        self.exit_code = exit_code


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
    ansi_pattern = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
    without_ansi = ansi_pattern.sub("", value)
    return without_ansi.replace("\r", "")


def promise_detected(text: str, expected: str | None) -> bool:
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
