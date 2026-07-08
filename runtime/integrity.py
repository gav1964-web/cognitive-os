"""Plugin integrity hashing."""

from __future__ import annotations

import hashlib
from pathlib import Path


_IGNORED_PARTS = {"__pycache__", ".pytest_cache"}
_IGNORED_SUFFIXES = {".pyc", ".pyo"}


def hash_plugin_dir(plugin_dir: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in plugin_dir.rglob("*") if item.is_file()):
        rel = path.relative_to(plugin_dir)
        if any(part in _IGNORED_PARTS for part in rel.parts):
            continue
        if path.suffix in _IGNORED_SUFFIXES:
            continue
        if rel.as_posix() == "plugin.json":
            content = _canonical_manifest(path)
        else:
            content = path.read_bytes()
        digest.update(rel.as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(content)
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def _canonical_manifest(path: Path) -> bytes:
    import json

    data = json.loads(path.read_text(encoding="utf-8"))
    data.pop("version_hash", None)
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
