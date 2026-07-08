"""Persistent counters for repeated runtime error classes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def increment_error_count(root: Path, *, capability_id: str, error_class: str, fingerprint: str) -> int:
    path = root / "artifacts" / "failures" / "error_counts.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    data = _read_counts(path)
    key = f"{capability_id}:{error_class}:{fingerprint}"
    data[key] = int(data.get(key, 0)) + 1
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return int(data[key])


def _read_counts(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))
