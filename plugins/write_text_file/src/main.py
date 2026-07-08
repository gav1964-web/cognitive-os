"""Write a scoped UTF-8 text file."""

from __future__ import annotations

from pathlib import Path


def run(payload: dict[str, object]) -> dict[str, object]:
    path = Path(str(payload["path"]))
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("write_text_file path must be workspace-relative and scoped")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(payload["text"]), encoding="utf-8")
    return {"path": path.as_posix()}
