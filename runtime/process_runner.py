"""Process-bound plugin entrypoint runner."""

from __future__ import annotations

import multiprocessing as mp
import queue
import sys
import traceback
from pathlib import Path
from typing import Any


class ProcessExecutionError(RuntimeError):
    """Raised when a child process reports an entrypoint failure."""

    def __init__(self, exception_type: str, message: str, child_traceback: str) -> None:
        super().__init__(message)
        self.exception_type = exception_type
        self.child_traceback = child_traceback


def run_entrypoint_in_process(
    root: Path,
    entrypoint: str,
    payload: dict[str, Any],
    *,
    timeout_seconds: float | None,
) -> dict[str, Any]:
    ctx = mp.get_context("spawn")
    result_queue: mp.Queue = ctx.Queue()
    process = ctx.Process(target=_child_main, args=(str(root), entrypoint, payload, result_queue))
    process.start()
    process.join(timeout_seconds)
    if process.is_alive():
        process.terminate()
        process.join(1)
        raise TimeoutError(f"process timeout: {entrypoint}")
    try:
        result = result_queue.get_nowait()
    except queue.Empty as exc:
        raise ProcessExecutionError("RuntimeError", f"child process exited without result: {entrypoint}", "") from exc
    if result["status"] == "error":
        raise ProcessExecutionError(str(result["exception_type"]), str(result["message"]), str(result["traceback"]))
    output = result["output"]
    if not isinstance(output, dict):
        raise TypeError(f"entrypoint output must be dict: {entrypoint}")
    return output


def _child_main(root: str, entrypoint: str, payload: dict[str, Any], result_queue: mp.Queue) -> None:
    try:
        if root not in sys.path:
            sys.path.insert(0, root)
        from runtime.plugin_loader import load_entrypoint

        fn = load_entrypoint(entrypoint)
        result_queue.put({"status": "ok", "output": fn(payload)})
    except BaseException as exc:
        result_queue.put(
            {
                "status": "error",
                "exception_type": type(exc).__name__,
                "message": str(exc),
                "traceback": "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
            }
        )
