"""Runtime quality metrics for registry scoring."""

from __future__ import annotations

import json
import os
import time
from contextlib import contextmanager
from pathlib import Path
from types import TracebackType
from typing import Any


def load_quality_metrics(root: Path) -> dict[str, dict[str, Any]]:
    path = _quality_path(root)
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def record_quality_event(
    root: Path,
    *,
    capability_id: str,
    success: bool,
    latency_ms: float | None = None,
) -> None:
    path = _quality_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with _QualityLock(root / "artifacts" / "registry" / "quality.lock"):
        metrics = load_quality_metrics(root)
        current = dict(metrics.get(capability_id, {}))
        runs = int(current.get("runs", 0)) + 1
        failures = int(current.get("failures", 0)) + (0 if success else 1)
        successes = int(current.get("successes", 0)) + (1 if success else 0)
        previous_avg = float(current.get("avg_latency_ms", 0.0))
        if latency_ms is None:
            avg_latency = previous_avg
        else:
            avg_latency = ((previous_avg * (runs - 1)) + float(latency_ms)) / runs
        metrics[capability_id] = {
            "runs": runs,
            "successes": successes,
            "failures": failures,
            "failure_rate": failures / runs,
            "avg_latency_ms": avg_latency,
        }
        path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _quality_path(root: Path) -> Path:
    return root / "artifacts" / "registry" / "quality.json"


class _QualityLock:
    def __init__(self, path: Path, *, timeout_seconds: float = 5.0, poll_seconds: float = 0.05) -> None:
        self.path = path
        self.timeout_seconds = timeout_seconds
        self.poll_seconds = poll_seconds
        self.fd: int | None = None

    def __enter__(self) -> "_QualityLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        deadline = time.monotonic() + self.timeout_seconds
        while True:
            try:
                self.fd = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(self.fd, str(os.getpid()).encode("ascii"))
                return self
            except FileExistsError:
                if time.monotonic() >= deadline:
                    raise TimeoutError(f"quality lock timeout: {self.path}")
                time.sleep(self.poll_seconds)

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass
