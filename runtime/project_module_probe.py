"""Client helpers for module import behavior probes."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


def open_module_import(project_dir: Path, probe: dict[str, Any], python_executable: Path | None = None) -> dict[str, Any]:
    entrypoint = str(probe.get("path") or "")
    if not entrypoint:
        return {"status": "skipped", "reason": "empty entrypoint"}
    repo_root = Path(__file__).resolve().parents[1]
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join([repo_root.as_posix(), project_dir.as_posix(), env.get("PYTHONPATH", "")])
    result = subprocess.run(
        [
            str(python_executable or sys.executable),
            "-m",
            "runtime.project_module_probe_runner",
            "--project-root",
            project_dir.as_posix(),
            "--entrypoint",
            entrypoint,
        ],
        capture_output=True,
        text=True,
        env=env,
        timeout=20,
    )
    if result.returncode != 0:
        return {"status": "error", "reason": result.stderr[-1000:] or "module probe subprocess failed", "entrypoint": entrypoint}
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"status": "error", "reason": result.stdout[-1000:], "entrypoint": entrypoint}


def module_shape_compatible(source: dict[str, Any], target: dict[str, Any]) -> bool:
    source_names = set(source.get("public_names", []))
    target_names = set(target.get("public_names", []))
    source_kinds = dict(source.get("attr_kinds") or {})
    target_kinds = dict(target.get("attr_kinds") or {})
    if source_names and source.get("public_source") == "__all__":
        if not source_names.issubset(target_names):
            return False
        return all(target_kinds.get(name) not in {None, "NoneType"} for name in source_names)
    common = source_names & target_names
    if common and any(target_kinds.get(name) in {None, "NoneType"} for name in common):
        return False
    return bool(target_names) or not source_names
