"""Run a project's provider health probe through its own CLI."""

from __future__ import annotations

import subprocess
import sys
import os
from pathlib import Path


def run(payload: dict[str, object]) -> dict[str, object]:
    root = _resolve_scoped_root(str(payload["root"]))
    probe = root / "tools" / "ping_llms.py"
    if not probe.is_file():
        raise ValueError("project_provider_probe requires tools/ping_llms.py")
    base_url = str(payload.get("base_url") or "http://127.0.0.1:9000")
    timeout_seconds = int(payload.get("timeout_seconds") or 60)
    max_providers = int(payload.get("max_providers") or 0)
    message = str(payload.get("message") or "Привет!")
    report_path = Path("reports") / "health_checks" / "cognitive_os_provider_probe.md"
    command = [
        sys.executable,
        "tools/ping_llms.py",
        "--start-server",
        "--base-url",
        base_url,
        "--timeout",
        str(timeout_seconds),
        "--max-providers",
        str(max_providers),
        "--message",
        message,
        "--out",
        report_path.as_posix(),
    ]
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    completed = subprocess.run(
        command,
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=max(timeout_seconds + 45, 90),
    )
    absolute_report = root / report_path
    return {
        "root": root.as_posix(),
        "command": command,
        "exit_code": int(completed.returncode),
        "status": "ok" if completed.returncode == 0 else "failed",
        "report_path": absolute_report.as_posix() if absolute_report.exists() else None,
        "stdout_tail": (completed.stdout or "")[-4000:],
        "stderr_tail": (completed.stderr or "")[-4000:],
    }


def _resolve_scoped_root(value: str) -> Path:
    raw = Path(value).expanduser()
    candidate = raw if raw.is_absolute() else Path.cwd() / raw
    resolved = candidate.resolve()
    if not resolved.exists() or not resolved.is_dir():
        raise ValueError("project_provider_probe root must point to an existing directory")
    allowed_roots = [Path.cwd().resolve(), Path.cwd().resolve().parent]
    if not any(_is_relative_to(resolved, allowed) for allowed in allowed_roots):
        raise ValueError("project_provider_probe root is outside the allowed project scope")
    return resolved


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False
