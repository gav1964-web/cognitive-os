"""Fresh-process boundary for executable acceptance analysis."""

from __future__ import annotations

import json
import subprocess
import sys
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
    try:
        completed = subprocess.run(
            [sys.executable, "-m", "runtime.executable_acceptance_worker"],
            cwd=str(root.resolve()),
            input=json.dumps(payload, ensure_ascii=False),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return _failure("isolated_process_failed", str(exc))
    try:
        return dict(json.loads(completed.stdout))
    except (json.JSONDecodeError, TypeError, ValueError):
        detail = completed.stderr[-1000:] or completed.stdout[-1000:]
        return _failure("isolated_process_invalid_result", detail)


def _failure(reason: str, detail: str) -> dict[str, Any]:
    return {
        "status": "failed",
        "summary": {"signal_strength": "", "reason": reason, "detail": detail},
        "source_code_changes": False,
    }
