"""Run one serializable call in a process with a hard wall-clock deadline."""

from __future__ import annotations

import json
import multiprocessing
import os
import tempfile
from pathlib import Path
from typing import Any, Callable


def run_bounded_process_call(
    target: Callable[..., Any], *, args: tuple[Any, ...] = (),
    kwargs: dict[str, Any] | None = None, timeout_seconds: float,
) -> tuple[Any | None, bool]:
    descriptor, raw_path = tempfile.mkstemp(prefix="cognitive-os-case-", suffix=".json")
    os.close(descriptor)
    path = Path(raw_path)
    context = multiprocessing.get_context("spawn")
    process = context.Process(target=_write_result, args=(target, args, kwargs or {}, path))
    try:
        process.start()
        process.join(max(0.01, float(timeout_seconds)))
        if process.is_alive():
            process.terminate()
            process.join(5)
            return None, True
        if process.exitcode != 0 or not path.stat().st_size:
            raise RuntimeError(f"bounded worker failed with exit code {process.exitcode}")
        envelope = json.loads(path.read_text(encoding="utf-8"))
        if envelope.get("status") != "ok":
            raise RuntimeError(str(envelope.get("error") or "bounded worker failed"))
        return envelope.get("result"), False
    finally:
        path.unlink(missing_ok=True)


def _write_result(
    target: Callable[..., Any], args: tuple[Any, ...], kwargs: dict[str, Any], path: Path,
) -> None:
    try:
        envelope = {"status": "ok", "result": target(*args, **kwargs)}
    except Exception as exc:
        envelope = {"status": "failed", "error": f"{type(exc).__name__}: {exc}"}
    path.write_text(json.dumps(envelope, ensure_ascii=False), encoding="utf-8")
