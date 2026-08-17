"""Read-only relative resource access for source-isolated callables."""

from __future__ import annotations

import builtins
from pathlib import Path
from typing import Any


def read_only_open_for(source: Path):
    def open_resource(file: Any, mode: str = "r", *args: Any, **kwargs: Any):
        if any(token in mode for token in ("w", "a", "x", "+")):
            raise PermissionError("source-isolated resource writes are forbidden")
        target = Path(file)
        if not target.is_absolute():
            resolved = _relative_resource(source, target)
            if resolved is not None:
                target = resolved
        return builtins.open(target, mode, *args, **kwargs)

    return open_resource


def _relative_resource(source: Path, relative: Path) -> Path | None:
    parent = source.resolve().parent
    for base in [parent, *list(parent.parents)[:8]]:
        candidate = (base / relative).resolve()
        try:
            candidate.relative_to(base)
        except ValueError:
            continue
        if candidate.is_file():
            return candidate
    return None
