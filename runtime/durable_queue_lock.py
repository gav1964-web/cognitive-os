"""Crash-recoverable lock used by the file-backed durable queue."""

from __future__ import annotations

import os
import time
from pathlib import Path
from types import TracebackType


class QueueLock:
    def __init__(self, path: Path, *, timeout_seconds: float = 5.0, poll_seconds: float = 0.05) -> None:
        self.path = path
        self.timeout_seconds = timeout_seconds
        self.poll_seconds = poll_seconds
        self.fd: int | None = None

    def acquire(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        deadline = time.monotonic() + self.timeout_seconds
        while True:
            try:
                self.fd = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(self.fd, str(os.getpid()).encode("ascii"))
                return
            except FileExistsError:
                if self._owned_by_dead_process():
                    try:
                        self.path.unlink()
                    except FileNotFoundError:
                        pass
                    continue
                if time.monotonic() >= deadline:
                    raise TimeoutError(f"queue lock timeout: {self.path}")
                time.sleep(self.poll_seconds)

    def _owned_by_dead_process(self) -> bool:
        try:
            owner = int(self.path.read_text(encoding="ascii").strip())
        except (FileNotFoundError, OSError, ValueError):
            return False
        return not _pid_alive(owner)

    def release(self) -> None:
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass

    def __enter__(self) -> "QueueLock":
        self.acquire()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.release()


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True
