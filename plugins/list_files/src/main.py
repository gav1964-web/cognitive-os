"""List files in a scoped directory."""

from __future__ import annotations

from pathlib import Path


def run(payload: dict[str, object]) -> dict[str, object]:
    path = Path(str(payload["path"]))
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("list_files path must be workspace-relative and scoped")
    files = sorted(item.as_posix() for item in path.rglob("*") if item.is_file())
    return {"files": files}
