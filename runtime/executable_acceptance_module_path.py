"""Resolve import names and roots from Python package layout."""

from __future__ import annotations

from pathlib import Path


def module_name_from_path(path_text: str, path: Path | None = None) -> str:
    if path is not None:
        name, _ = package_import_target(path)
        if name:
            return name
    parts = list(Path(path_text).with_suffix("").parts)
    if parts and parts[0] == "src":
        parts = parts[1:]
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def package_import_root(path: Path | None) -> Path | None:
    return package_import_target(path)[1] if path is not None else None


def package_import_target(path: Path) -> tuple[str, Path | None]:
    resolved = path.resolve()
    parts = [] if resolved.stem == "__init__" else [resolved.stem]
    parent = resolved.parent
    while (parent / "__init__.py").is_file():
        parts.insert(0, parent.name)
        parent = parent.parent
    return (".".join(parts), parent) if parts and parent != resolved.parent else ("", None)
