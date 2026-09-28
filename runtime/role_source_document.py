"""Bounded parsed-source cache for repeated role context lookups."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from .python_parser_compatibility import parse_compatible_source


def load_source_document(path: Path):
    stat = path.stat()
    return _load_source_document(str(path.resolve()), stat.st_mtime_ns, stat.st_size)


@lru_cache(maxsize=64)
def _load_source_document(path_text: str, _mtime_ns: int, _size: int):
    path = Path(path_text)
    text = path.read_text(encoding="utf-8", errors="replace")
    tree, _ = parse_compatible_source(text, path.as_posix())
    return text, text.splitlines(), tree
