"""Resolve role-owned target paths against repository source layouts."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .executable_acceptance_policy import target_path_resolution_policy


def resolve_target_path(project_dir: Path, path_text: str) -> dict[str, Any]:
    root = project_dir.resolve()
    direct = (root / path_text).resolve()
    try:
        direct.relative_to(root)
    except ValueError:
        return {"path": direct, "path_text": path_text, "reason": "target_outside_project"}
    if direct.is_file():
        return {"path": direct, "path_text": direct.relative_to(root).as_posix(), "reason": ""}

    policy = target_path_resolution_policy()
    if not policy["enabled"]:
        return {"path": direct, "path_text": path_text, "reason": "target_file_missing"}
    suffix = Path(path_text).as_posix().lstrip("./")
    if not suffix.endswith(".py") or not suffix:
        return {"path": direct, "path_text": path_text, "reason": "target_file_missing"}

    ignored = set(policy["ignored_directories"])
    matches: list[Path] = []
    inspected = 0
    for candidate in root.rglob(Path(suffix).name):
        relative = candidate.relative_to(root)
        if any(part in ignored for part in relative.parts):
            continue
        inspected += 1
        if inspected > policy["max_candidate_files"]:
            break
        relative_text = relative.as_posix()
        if candidate.is_file() and (relative_text == suffix or relative_text.endswith(f"/{suffix}")):
            matches.append(candidate.resolve())
            if len(matches) > policy["max_unique_matches"]:
                break
    if len(matches) == 1:
        match = matches[0]
        return {"path": match, "path_text": match.relative_to(root).as_posix(), "reason": ""}
    if len(matches) > 1:
        detail = ", ".join(path.relative_to(root).as_posix() for path in matches)
        return {"path": direct, "path_text": path_text, "reason": "target_file_ambiguous", "detail": detail}
    return {"path": direct, "path_text": path_text, "reason": "target_file_missing"}
