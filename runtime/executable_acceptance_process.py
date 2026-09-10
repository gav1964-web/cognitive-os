"""Fresh-process boundary for executable acceptance analysis."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


def run_executable_acceptance_process(
    *, root: Path, project_dir: Path, test_plan: dict[str, Any], work_dir: Path,
    timeout_seconds: int, executable_policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        "root": str(root.resolve()),
        "project_dir": str(project_dir.resolve()),
        "test_plan": test_plan,
        "work_dir": str(work_dir.resolve()),
        "executable_policy": executable_policy,
    }
    process: subprocess.Popen[str] | None = None
    with tempfile.TemporaryFile(mode="w+b") as stdin_file, \
            tempfile.TemporaryFile(mode="w+b") as stdout_file, \
            tempfile.TemporaryFile(mode="w+b") as stderr_file:
        stdin_file.write(json.dumps(payload, ensure_ascii=False).encode("utf-8")); stdin_file.seek(0)
        try:
            process = subprocess.Popen(
                [sys.executable, "-m", "runtime.executable_acceptance_worker"],
                cwd=str(root.resolve()), stdin=stdin_file, stdout=stdout_file, stderr=stderr_file,
                text=True, encoding="utf-8", errors="replace", **_process_group_options(),
            )
            process.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            if process is not None:
                _terminate_process_tree(process)
            return _failure(
                "isolated_process_failed", f"isolated process timed out after {timeout_seconds}s",
            )
        except OSError as exc:
            if process is not None:
                _terminate_process_tree(process)
            return _failure("isolated_process_failed", str(exc))
        stdout_file.seek(0); stderr_file.seek(0)
        stdout = stdout_file.read().decode("utf-8", errors="replace")
        stderr = stderr_file.read().decode("utf-8", errors="replace")
    try:
        return dict(json.loads(stdout))
    except (json.JSONDecodeError, TypeError, ValueError):
        detail = stderr[-1000:] or stdout[-1000:]
        return _failure("isolated_process_invalid_result", detail)


def _process_group_options() -> dict[str, Any]:
    if os.name == "nt":
        return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    return {"start_new_session": True}


def _terminate_process_tree(process: subprocess.Popen[str]) -> None:
    if os.name == "nt":
        try:
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10,
            )
        except (OSError, subprocess.SubprocessError):
            pass
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except (OSError, ProcessLookupError):
            pass
    if process.poll() is None:
        process.kill()
    try:
        process.wait(timeout=5)
    except (OSError, subprocess.SubprocessError):
        pass


def _failure(reason: str, detail: str) -> dict[str, Any]:
    return {
        "status": "failed",
        "summary": {"signal_strength": "", "reason": reason, "detail": detail},
        "source_code_changes": False,
    }
