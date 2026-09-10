"""Validation for project-scoped native regression targets."""

from __future__ import annotations

from pathlib import Path


def existing_regression_targets(project: Path, candidates: list[object]) -> list[str]:
    selected: list[str] = []
    for value in candidates:
        target = str(value).replace("\\", "/").strip()
        path_text = target.split("::", 1)[0]
        path = Path(path_text)
        if (
            not target
            or target.startswith("-")
            or path.is_absolute()
            or ".." in path.parts
            or not (project / path).exists()
        ):
            continue
        if target not in selected:
            selected.append(target)
    return selected
