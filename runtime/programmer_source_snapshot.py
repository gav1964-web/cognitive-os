"""Snapshot the Programmer's declared writable files for its execution receipt."""
import shutil
from pathlib import Path
from typing import Any


def _snapshot_writable_files(execution_dir: Path, project_dir: Path, implementation_plan: dict[str, Any]) -> list[dict[str, Any]]:
    snapshot_dir = execution_dir / "source_snapshot"
    copied = []
    for file_name in _expected_files(implementation_plan):
        source = (project_dir / file_name).resolve()
        try:
            source.relative_to(project_dir.resolve())
        except ValueError:
            copied.append({"file": file_name, "status": "blocked_outside_project"})
            continue
        if not source.is_file():
            copied.append({"file": file_name, "status": "missing"})
            continue
        destination = snapshot_dir / file_name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        copied.append({"file": file_name, "status": "copied", "snapshot": destination.as_posix()})
    return copied


def _expected_files(implementation_plan: dict[str, Any]) -> list[str]:
    files = []
    for item in implementation_plan.get("expected_files", []):
        path = str(item).split(":", 1)[0]
        if path and path not in files:
            files.append(path)
    return files[:8]
