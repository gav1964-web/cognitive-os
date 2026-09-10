"""Process, git-metadata and digest helpers for native failure intake."""

from __future__ import annotations

import hashlib
import os
import re
import signal
import shutil
import subprocess
from pathlib import Path
from typing import Any

from cognitive_replay.bounded_process import _run_bounded_process, _terminate_process_tree
from cognitive_replay.version import _project_version_hint

def _copy_git_build_metadata(project: Path, sandbox: Path, intake: dict[str, Any]) -> bool:
    if not bool(intake.get("preserve_bounded_git_build_metadata", True)):
        return False
    pyproject = project / "pyproject.toml"
    git_marker = project / ".git"
    if not pyproject.is_file():
        return False
    try:
        content = pyproject.read_text(encoding="utf-8")
    except OSError:
        return False
    markers = (
        "[tool.setuptools-git-versioning]",
        "[tool.setuptools_scm]",
        "[tool.hatch.version]",
        "hatch-vcs",
    )
    if not any(marker in content for marker in markers):
        return False
    git_dir, worktree_head = _git_metadata_source(git_marker)
    if git_dir is None:
        return False
    maximum_files = int(intake.get("maximum_git_metadata_files") or 5000)
    maximum_bytes = int(intake.get("maximum_git_metadata_bytes") or 20_000_000)
    files = [path for path in git_dir.rglob("*") if path.is_file()]
    if worktree_head is not None and worktree_head not in files:
        files.append(worktree_head)
    if len(files) > maximum_files:
        return False
    try:
        total_bytes = sum(path.stat().st_size for path in files)
    except OSError:
        return False
    if total_bytes > maximum_bytes:
        return False
    try:
        shutil.copytree(git_dir, sandbox / ".git")
        if worktree_head is not None:
            shutil.copy2(worktree_head, sandbox / ".git" / "HEAD")
    except OSError:
        return False
    return True

def _git_metadata_source(git_marker: Path) -> tuple[Path | None, Path | None]:
    if git_marker.is_dir():
        return git_marker, None
    if not git_marker.is_file():
        return None, None
    try:
        marker = git_marker.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError):
        return None, None
    match = re.fullmatch(r"gitdir:\s*(.+)", marker)
    if match is None:
        return None, None
    linked_dir = Path(match.group(1))
    if not linked_dir.is_absolute():
        linked_dir = git_marker.parent / linked_dir
    try:
        linked_dir = linked_dir.resolve(strict=True)
    except OSError:
        return None, None
    linked_head = linked_dir / "HEAD"
    if not linked_dir.is_dir() or not linked_head.is_file():
        return None, None
    common_marker = linked_dir / "commondir"
    if not common_marker.is_file():
        return linked_dir, None
    try:
        common_value = common_marker.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError):
        return None, None
    if not common_value:
        return None, None
    common_dir = Path(common_value)
    if not common_dir.is_absolute():
        common_dir = linked_dir / common_dir
    try:
        common_dir = common_dir.resolve(strict=True)
    except OSError:
        return None, None
    if not common_dir.is_dir() or not (common_dir / "objects").is_dir():
        return None, None
    return common_dir, linked_head

def _copy_project(source: Path, destination: Path, intake: dict[str, Any]) -> None:
    excluded = {str(value) for value in intake.get("excluded_copy_directories") or []}
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, destination, ignore=shutil.ignore_patterns(*sorted(excluded)))

def _project_digest(project: Path) -> str:
    digest = hashlib.sha256()
    excluded = {
        ".git", ".hg", ".pytest_cache", ".pytest-native-intake", ".mypy_cache",
        ".ruff_cache", "__pycache__", ".venv", "venv", ".native-user", ".nfi",
    }
    for path in sorted(item for item in project.rglob("*") if item.is_file() and not set(item.relative_to(project).parts).intersection(excluded)):
        digest.update(path.relative_to(project).as_posix().encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()

def _slug(value: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in value).strip("_")[:100]
