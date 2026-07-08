"""Read a scoped UTF-8 text file."""

from __future__ import annotations

from pathlib import Path


def run(payload: dict[str, object]) -> dict[str, object]:
    path = Path(str(payload["path"]))
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("read_text_file path must be workspace-relative and scoped")
    return {"text": path.read_text(encoding="utf-8")}
