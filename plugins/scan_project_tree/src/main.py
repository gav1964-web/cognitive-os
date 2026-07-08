"""Scan a project tree with deterministic limits."""

from __future__ import annotations

from pathlib import Path
from typing import Any


DEFAULT_EXCLUDED_DIRS = {
    ".git",
    ".hg",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    ".vscode",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "venv",
}

NOTABLE_NAMES = {
    ".env",
    "dockerfile",
    "makefile",
    "package.json",
    "pyproject.toml",
    "readme.md",
    "requirements.txt",
    "setup.py",
}


def run(payload: dict[str, object]) -> dict[str, object]:
    root = _resolve_scoped_path(str(payload["path"]))
    max_files = int(payload.get("max_files", 5000))
    max_depth = int(payload.get("max_depth", 8))
    include_hidden = bool(payload.get("include_hidden", False))
    if max_files < 1:
        raise ValueError("max_files must be positive")
    if max_depth < 0:
        raise ValueError("max_depth must be non-negative")

    files: list[dict[str, Any]] = []
    directories: list[str] = []
    extensions: dict[str, int] = {}
    notable_files: list[str] = []
    skipped = {"directories": 0, "files": 0, "too_deep": 0, "truncated_files": 0}
    stack = [(root, 0)]
    while stack:
        current, parent_depth = stack.pop()
        for item in sorted(current.iterdir(), key=lambda path: path.name.lower()):
            relative = item.relative_to(root)
            depth = len(relative.parts) - 1
            rel_path = relative.as_posix()
            if _is_noise_path(relative, include_hidden):
                if item.is_dir():
                    skipped["directories"] += 1
                else:
                    skipped["files"] += 1
                continue
            if item.is_dir():
                if parent_depth >= max_depth:
                    skipped["too_deep"] += 1
                    continue
                directories.append(rel_path)
                stack.append((item, parent_depth + 1))
                continue
            if not item.is_file():
                skipped["files"] += 1
                continue
            if len(files) >= max_files:
                skipped["truncated_files"] += 1
                continue
            _append_file(files, extensions, notable_files, item, rel_path, depth)

    return {
        "root": root.as_posix(),
        "files": files,
        "directories": directories,
        "counts": {
            "files": len(files),
            "directories": len(directories),
            "truncated": skipped["truncated_files"] > 0 or skipped["too_deep"] > 0,
        },
        "extensions": dict(sorted(extensions.items())),
        "notable_files": sorted(notable_files),
        "skipped": skipped,
    }


def _append_file(
    files: list[dict[str, Any]],
    extensions: dict[str, int],
    notable_files: list[str],
    item: Path,
    rel_path: str,
    depth: int,
) -> None:
    extension = item.suffix.lower() or "<none>"
    extensions[extension] = extensions.get(extension, 0) + 1
    lower_name = item.name.lower()
    if lower_name in NOTABLE_NAMES or lower_name.endswith((".bat", ".sh", ".ps1")):
        notable_files.append(rel_path)
    files.append(
        {
            "path": rel_path,
            "extension": extension,
            "size_bytes": item.stat().st_size,
            "depth": depth,
        }
    )


def _is_noise_path(relative: Path, include_hidden: bool) -> bool:
    parts = relative.parts
    if any(part in DEFAULT_EXCLUDED_DIRS for part in parts):
        return True
    return not include_hidden and any(part.startswith(".") for part in parts)


def _resolve_scoped_path(value: str) -> Path:
    raw = Path(value).expanduser()
    candidate = raw if raw.is_absolute() else Path.cwd() / raw
    resolved = candidate.resolve()
    if not resolved.exists() or not resolved.is_dir():
        raise ValueError("scan_project_tree path must point to an existing directory")
    allowed_roots = [Path.cwd().resolve(), Path.cwd().resolve().parent]
    if not any(_is_relative_to(resolved, allowed) for allowed in allowed_roots):
        raise ValueError("scan_project_tree path is outside the allowed project scope")
    return resolved


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False
