"""Filesystem-safe Python module resolution for native failure binding."""

from __future__ import annotations

from pathlib import Path


def _project_relative_traceback_path(project: Path, raw_path: str) -> str | None:
    candidate = Path(raw_path)
    if candidate.is_absolute():
        try:
            relative = candidate.resolve().relative_to(project.resolve())
        except (OSError, ValueError):
            return None
        return relative.as_posix()

    normalized = raw_path.replace("\\", "/")
    direct = Path(normalized)
    if ".." not in direct.parts and (project / direct).is_file():
        return direct.as_posix().lstrip("./")

    # Intake copies always anchor the project below a bounded `p` directory.
    parts = [part for part in normalized.split("/") if part not in {"", "."}]
    for index in range(len(parts) - 1, -1, -1):
        if parts[index].lower() != "p":
            continue
        suffix = Path(*parts[index + 1:])
        if suffix.parts and ".." not in suffix.parts and (project / suffix).is_file():
            return suffix.as_posix()
    return None


def _python_module_path(project: Path, parts: list[str]) -> Path | None:
    path = _python_module_path_any(project, parts)
    return path if path is not None and _is_production_path(project, path) else None


def _python_module_path_any(project: Path, parts: list[str]) -> Path | None:
    for root in (project / "src", project):
        module = root.joinpath(*parts).with_suffix(".py")
        if module.is_file() and _entry_case_matches(module):
            return module
        package = root.joinpath(*parts, "__init__.py")
        if (
            package.is_file()
            and _entry_case_matches(package)
            and _entry_case_matches(package.parent)
        ):
            return package
    return None


def _entry_case_matches(path: Path) -> bool:
    try:
        return any(item.name == path.name for item in path.parent.iterdir())
    except OSError:
        return False


def _is_production_path(project: Path, path: Path) -> bool:
    relative = path.relative_to(project)
    parts = {part.lower() for part in relative.parts}
    return not parts.intersection({"test", "tests", "testing"}) and not path.name.startswith("test_")
