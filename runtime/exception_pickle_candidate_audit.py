"""AST audit for custom exceptions whose default pickle replay cannot call __init__."""

from __future__ import annotations

import ast
import os
from pathlib import Path
from typing import Any

# Detector knowledge is owned by the exception_pickle competency.
from plugins.exception_pickle.src.candidates import _candidate, _exception_shaped, _has_reconstruction_hook  # noqa: F401


def audit_exception_pickle_candidates(
    *, projects: list[dict[str, Any]], workspace_root: Path, maximum_files_per_project: int = 200
) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    scanned_projects = 0
    scanned_files = 0
    parse_failures = 0
    for project in projects:
        if project.get("exposure") != "historically_exposed":
            continue
        root = (workspace_root / str(project.get("project_root") or "")).resolve()
        try:
            root.relative_to(workspace_root.resolve())
        except ValueError:
            continue
        if not root.is_dir() or "pytest-socket" in str(project.get("canonical_project") or ""):
            continue
        scanned_projects += 1
        files = _bounded_python_files(root, maximum_files_per_project)
        project_candidates: list[dict[str, Any]] = []
        for path in files:
            if any(part in {".git", ".venv", "venv", "__pycache__"} for part in path.parts):
                continue
            try:
                source = path.read_text(encoding="utf-8")
            except (OSError, UnicodeError):
                continue
            scanned_files += 1
            if "__init__" not in source or "super().__init__" not in source:
                continue
            try:
                tree = ast.parse(source, filename=str(path))
            except SyntaxError:
                parse_failures += 1
                continue
            local_classes = {
                node.name: node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)
            }
            for owner in (node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)):
                row = _candidate(owner, local_classes=local_classes)
                if row is None:
                    continue
                row.update({
                    "path": path.relative_to(root).as_posix(),
                    "project": project.get("project"),
                    "canonical_project": project.get("canonical_project"),
                    "owner": project.get("owner"),
                    "project_root": str(project.get("project_root") or ""),
                })
                project_candidates.append(row)
        if project_candidates:
            pickle_signals = _project_pickle_signals(root, files)
            for row in project_candidates:
                class_name = str(row["class_name"])
                matching = [signal for signal in pickle_signals if class_name in signal["text"]]
                row["pickle_test_signals"] = [signal["path"] for signal in matching[:8]]
                row["score"] = (
                    4 * bool(matching)
                    + 2 * bool(row["stored_constructor_parameters"])
                    + min(3, len(row["required_constructor_parameters"]))
                    + 2 * bool(row["formatted_super_argument"])
                )
                candidates.append(row)
    candidates.sort(key=lambda row: (-int(row["score"]), str(row["canonical_project"]), str(row["path"])))
    return {
        "artifact_type": "ExceptionPickleCandidateAudit",
        "status": "candidates_found" if candidates else "no_candidates",
        "candidate_count": len(candidates),
        "candidates": candidates,
        "scan": {
            "project_scope": "historically_exposed_only",
            "projects_scanned": scanned_projects,
            "python_files_scanned": scanned_files,
            "parse_failures": parse_failures,
            "maximum_files_per_project": maximum_files_per_project,
            "untouched_holdout_scanned": False,
        },
        "safety": {"source_apply": False, "promotion_applied": False},
    }


def _project_pickle_signals(root: Path, files: list[Path]) -> list[dict[str, str]]:
    signals: list[dict[str, str]] = []
    for path in files:
        relative = path.relative_to(root).as_posix()
        if not any(part in {"test", "tests"} or part.startswith("test_") for part in path.parts):
            continue
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        if any(token in source for token in ("pickle.dumps", "pickle.loads", "pickleable", "picklable")):
            signals.append({"path": relative, "text": source})
    return signals


def _bounded_python_files(root: Path, maximum: int) -> list[Path]:
    files: list[Path] = []

    def ignore_walk_error(_error: OSError) -> None:
        return None

    for directory, names, filenames in os.walk(root, onerror=ignore_walk_error):
        names[:] = sorted(
            name for name in names
            if name not in {".git", ".venv", "venv", "__pycache__", "node_modules"}
        )
        base = Path(directory)
        for filename in sorted(filenames):
            if filename.endswith(".py"):
                files.append(base / filename)
                if len(files) >= maximum:
                    return files
    return files
