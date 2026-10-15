from __future__ import annotations

import io
import traceback
from contextlib import redirect_stderr, redirect_stdout
from typing import Any, Callable

from PySide6.QtCore import QThread, Signal


class _SignalStream(io.TextIOBase):
    def __init__(self, signal: Signal) -> None:
        super().__init__()
        self._signal = signal

    def write(self, text: str) -> int:
        if text:
            for line in text.splitlines():
                stripped = line.strip()
                if stripped:
                    self._signal.emit(stripped)
        return len(text)

    def flush(self) -> None:
        return None


class TaskWorker(QThread):
    started_task = Signal(str)
    log_message = Signal(str)
    completed = Signal(object)
    failed = Signal(str)

    def __init__(self, title: str, func: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        super().__init__()
        self.title = title
        self.func = func
        self.args = args
        self.kwargs = kwargs

    def run(self) -> None:
        self.started_task.emit(self.title)
        output = _SignalStream(self.log_message)

        try:
            with redirect_stdout(output), redirect_stderr(output):
                result = self.func(*self.args, **self.kwargs)
        except Exception:
            self.failed.emit(traceback.format_exc())
            return

        self.completed.emit(result)
