"""Detect small Python support surfaces without an owned Python product boundary."""

from __future__ import annotations

import os
from pathlib import Path

from runtime.source_target_policy import scope_policy_int, scope_policy_list


_EXCLUDED_DIRS = {".git", ".hg", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache"}
_DJANGO_SCAFFOLD_FILES = {"__init__.py", "asgi.py", "manage.py", "settings.py", "urls.py", "wsgi.py"}


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
    if not python_source_files:
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


def native_dominated_monorepo(native_files: list[Path], py_files: list[Path], root_package: str | None) -> bool:
    minimum = scope_policy_int("native_monorepo_min_files", 500)
    ratio = scope_policy_int("native_monorepo_files_per_python", 5)
    return not root_package and len(native_files) >= minimum and len(native_files) >= max(1, len(py_files)) * ratio


def foreign_language_dominated_monorepo(
    foreign_files: list[Path], py_files: list[Path], root_package: str | None
) -> bool:
    minimum = scope_policy_int("foreign_monorepo_min_files", 500)
    ratio = scope_policy_int("foreign_monorepo_files_per_python", 8)
    return not root_package and len(foreign_files) >= minimum and len(foreign_files) >= max(1, len(py_files)) * ratio


def fixture_only_python_corpus(path: Path, py_files: list[Path], root_package: str | None) -> bool:
    if root_package or not py_files:
        return False
    markers = {"fixture", "fixtures", "test", "tests", "test-project", "test-resources", "testdata"}
    return all(markers.intersection(part.lower() for part in source.relative_to(path).parts[:-1]) for source in py_files)


def scripts_only_python_support(path: Path, py_files: list[Path], root_package: str | None) -> bool:
    if root_package or not py_files or any((path / name).is_file() for name in ("pyproject.toml", "setup.py", "setup.cfg")):
        return False
    return all(source.relative_to(path).parts[0].lower() in {"script", "scripts", "tools"} for source in py_files)


def documentation_deployment_demo(path: Path, python_source_files: list[Path], root_package: str | None) -> bool:
    if root_package or not python_source_files or len(python_source_files) > 20:
        return False
    if any((path / name).is_file() for name in ("pyproject.toml", "setup.py", "setup.cfg")):
        return False
    readmes = [file for file in path.iterdir() if file.is_file() and file.name.lower().startswith("readme")]
    infra = set(scope_policy_list("deployment_template_infra_files")) or {
        "docker-compose.yml", "dockerfile", "stack.yml"
    }
    top_files = {file.name.lower() for file in path.iterdir() if file.is_file()}
    if not readmes or not top_files.intersection(infra):
        return False
    if max(file.stat().st_size for file in readmes) >= 20_000 and len(top_files & infra) >= 2:
        return True
    markers = [item.lower() for item in scope_policy_list("deployment_template_markers")]
    text = "\n".join(file.read_text(encoding="utf-8", errors="ignore")[:40_000] for file in readmes).lower()
    return bool(markers) and any(marker in text for marker in markers)


def _non_python_file_count(path: Path, *, stop_at: int) -> int:
    count = 0
    for current, dirs, files in os.walk(path, topdown=True, onerror=lambda _exc: None):
        dirs[:] = [name for name in dirs if name not in _EXCLUDED_DIRS]
        count += sum(Path(name).suffix.lower() not in {".py", ".pyi"} for name in files)
        if count >= stop_at:
            return count
    return count
