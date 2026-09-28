"""Plugin integrity hashing."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
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
    for label, path in implementation_files(plugin_dir):
        digest.update(label.encode("utf-8") + b"\0")
        digest.update(path.read_bytes() + b"\0")
    return "sha256:" + digest.hexdigest()


def implementation_files(plugin_dir: Path) -> list[tuple[str, Path]]:
    """Resolve declared installed implementation packages without executing them."""
    manifest_path = plugin_dir / "plugin.json"
    if not manifest_path.is_file():
        return []
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    packages = manifest.get("implementation_packages", [])
    if not isinstance(packages, list) or len(packages) > 8:
        raise ValueError("implementation_packages must be a bounded list")
    if any(not isinstance(name, str) or not re.fullmatch(r"[A-Za-z_]\w*", name) for name in packages):
        raise ValueError("implementation package must be a top-level Python package")
    files = []
    for name in sorted(set(packages)):
        spec = importlib.util.find_spec(name)
        if spec is None or not spec.origin or not spec.submodule_search_locations:
            raise ValueError(f"implementation package is not installed: {name}")
        directory = Path(spec.origin).resolve().parent
        for path in sorted(directory.rglob("*")):
            relative = path.relative_to(directory)
            if (not path.is_file() or any(part in _IGNORED_PARTS for part in relative.parts)
                    or path.suffix in _IGNORED_SUFFIXES):
                continue
            if not path.resolve().is_relative_to(directory):
                raise ValueError(f"implementation file escapes package: {path}")
            files.append((f"implementation/{name}/{relative.as_posix()}", path))
    return files


def _canonical_manifest(path: Path) -> bytes:
    import json

    data = json.loads(path.read_text(encoding="utf-8"))
    data.pop("version_hash", None)
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
