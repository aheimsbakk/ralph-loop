from __future__ import annotations

import signal as signal_module
from types import FrameType
from typing import Any, Callable
import threading


class SignalHandler:
    """Installs and restores signal handlers, manages the interruption event flag."""

    def __init__(self) -> None:
        self._previous_handlers: dict[int, Any] = {}
        self._interrupted = threading.Event()
        self._signum: int | None = None
        self._stop_callback: Callable[[], str] | None = None

    @property
    def interrupted(self) -> threading.Event:
        return self._interrupted

    @property
    def signum(self) -> int | None:
        return self._signum

    def set_stop_callback(self, callback: Callable[[], str]) -> None:
        self._stop_callback = callback

    def install(self) -> None:
        for signum in (signal_module.SIGINT, signal_module.SIGTERM):
            self._previous_handlers[signum] = signal_module.getsignal(signum)
            signal_module.signal(signum, self._handle_signal)

    def restore(self) -> None:
        for signum, handler in self._previous_handlers.items():
            signal_module.signal(signum, handler)
        self._previous_handlers.clear()

    def _handle_signal(self, signum: int, _frame: FrameType | None) -> None:
        if self._stop_callback is not None:
            self._stop_callback()
        self._signum = signum
        self._interrupted.set()
