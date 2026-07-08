"""Select a dotted path from a JSON-like object."""

from __future__ import annotations


def run(payload: dict[str, object]) -> dict[str, object]:
    current = payload["data"]
    for part in str(payload["path"]).split("."):
        if isinstance(current, dict):
            current = current[part]
        elif isinstance(current, list):
            current = current[int(part)]
        else:
            raise ValueError("path cannot continue through scalar")
    return {"value": current}

