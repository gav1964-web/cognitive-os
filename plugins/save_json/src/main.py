"""Scoped JSON writer for the MVP."""

from __future__ import annotations

import json
from pathlib import Path


def run(payload: dict[str, object]) -> dict[str, object]:
    path = Path(str(payload["path"]))
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("save_json path must be workspace-relative and scoped")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload["data"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"path": path.as_posix()}

