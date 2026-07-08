"""Inspect whether Python packages are importable in the current environment."""

from __future__ import annotations

import importlib.metadata
import importlib.util


def run(payload: dict[str, object]) -> dict[str, object]:
    packages = [str(item) for item in payload.get("packages", [])]
    rows = []
    for name in packages:
        available = importlib.util.find_spec(name) is not None
        rows.append({"package": name, "available": available, "version": _version(name) if available else None})
    return {"packages": rows}


def _version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None
