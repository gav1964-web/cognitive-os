"""Detect small Python support surfaces without an owned Python product boundary."""

from __future__ import annotations

import os
from pathlib import Path

from runtime.source_target_policy import scope_policy_int, scope_policy_list


_EXCLUDED_DIRS = {".git", ".hg", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache"}
_DJANGO_SCAFFOLD_FILES = {"asgi.py", "manage.py", "settings.py", "urls.py", "wsgi.py"}


def incidental_polyglot_python_boundary(
    path: Path, python_source_files: list[Path], root_package: str | None, *, has_manifest: bool
) -> bool:
    if has_manifest or root_package or len(python_source_files) < 3:
        return False
    if any(source.parent == path for source in python_source_files):
        return False
    maximum = scope_policy_int("incidental_polyglot_python_max_files", 8)
    minimum_other = scope_policy_int("incidental_polyglot_non_python_min_files", 50)
    if len(python_source_files) > maximum:
        return False
    return _non_python_file_count(path, stop_at=minimum_other) >= minimum_other


def django_scaffold_without_owned_app(
    python_source_files: list[Path], root_package: str | None, *, has_manifest: bool
) -> bool:
    if has_manifest or root_package or not python_source_files:
        return False
    names = {path.name.lower() for path in python_source_files}
    return len(python_source_files) >= 3 and names <= _DJANGO_SCAFFOLD_FILES


def incidental_context_scripts(path: Path, python_source_files: list[Path], root_package: str | None) -> bool:
    if root_package or not 1 <= len(python_source_files) <= 2:
        return False
    if any((path / name).is_file() for name in ("pyproject.toml", "setup.py", "setup.cfg")):
        return False
    roots = set(scope_policy_list("incidental_python_context_roots"))
    return bool(roots) and all(source.relative_to(path).parts[0].lower() in roots for source in python_source_files)


def _non_python_file_count(path: Path, *, stop_at: int) -> int:
    count = 0
    for current, dirs, files in os.walk(path, topdown=True, onerror=lambda _exc: None):
        dirs[:] = [name for name in dirs if name not in _EXCLUDED_DIRS]
        count += sum(Path(name).suffix.lower() not in {".py", ".pyi"} for name in files)
        if count >= stop_at:
            return count
    return count
