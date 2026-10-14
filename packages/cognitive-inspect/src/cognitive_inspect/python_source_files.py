"""Recognize Python modules and extensionless Python executables."""

from __future__ import annotations

import os
from pathlib import Path


EXCLUDED_DIRS = {".git", ".hg", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache"}


def is_python_source_file(path: Path) -> bool:
    if not path.is_file():
        return False
    if path.suffix.lower() in {".py", ".pyw"}:
        return True
    if path.suffix:
        return False
    try:
        first_line = path.open("rb").readline(256).lower()
    except OSError:
        return False
    return first_line.startswith(b"#!") and b"python" in first_line


def iter_python_source_files(root: Path, *, limit: int | None = None):
    count = 0
    for current, dirs, files in os.walk(root, topdown=True, onerror=lambda _exc: None):
        dirs[:] = sorted(name for name in dirs if name not in EXCLUDED_DIRS and not name.startswith("."))
        for name in sorted(files):
            path = Path(current) / name
            if not is_python_source_file(path):
                continue
            yield path
            count += 1
            if limit is not None and count >= limit:
                return


def is_python_source_ref(source: str) -> bool:
    source = str(source or "")
    path_text = source.split(":", 1)[0].replace("\\", "/")
    name = Path(path_text).name
    suffix = Path(name).suffix.lower()
    return bool(name and not name.startswith("[") and " " not in name and (suffix in {".py", ".pyw"} or not suffix and ":" in source))
