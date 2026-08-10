"""Subprocess runner for safe module import behavior probes."""

from __future__ import annotations

import argparse
import json
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from .project_module_probe_stubs import import_with_dependency_stubs, install_version_fallbacks
from .project_module_static_shape import static_module_shape


PROBE_VERSION = "0.0.0"


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--entrypoint", required=True)
    args = parser.parse_args()
    result = probe_module_import(Path(args.project_root), args.entrypoint)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


def probe_module_import(project_root: Path, entrypoint: str) -> dict[str, Any]:
    path = project_root / entrypoint
    if not path.exists() or path.suffix != ".py":
        return {"status": "skipped", "reason": "entrypoint not found", "entrypoint": entrypoint}
    try:
        module_name = _module_name(path.relative_to(project_root))
        with _path_front(*_import_roots(project_root, path)):
            install_version_fallbacks(module_name)
            loaded = import_with_dependency_stubs(project_root, module_name)
        return {
            "status": "ok",
            "entrypoint": entrypoint,
            "module": module_name,
            "shape": _module_shape(loaded["module"]),
            "dependency_stubs": loaded["dependency_stubs"],
        }
    except Exception as exc:
        fallback = _static_shape_fallback(path, entrypoint, module_name, exc)
        if fallback:
            return fallback
        return {"status": "error", "entrypoint": entrypoint, "reason": f"{type(exc).__name__}: {exc}"}


def _module_name(relative: Path) -> str:
    parts = list(relative.with_suffix("").parts)
    if "src" in parts[:-1]:
        parts = parts[parts.index("src") + 1 :]
    elif "lib" in parts[:-1]:
        parts = parts[parts.index("lib") + 1 :]
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    clean = [part for part in parts if part.replace("_", "").isalnum()]
    return ".".join(clean) or "project_probe_target"


def _import_roots(project_root: Path, path: Path) -> list[Path]:
    roots = [project_root]
    parts = path.relative_to(project_root).parts
    for marker in ("src", "lib"):
        if marker in parts[:-1]:
            roots.append(project_root.joinpath(*parts[: parts.index(marker) + 1]))
    return roots


def _module_shape(module: Any) -> dict[str, Any]:
    exported = getattr(module, "__all__", None)
    if isinstance(exported, (list, tuple)):
        names = [str(item) for item in exported if isinstance(item, str)]
        source = "__all__"
    else:
        names = [name for name in vars(module) if not name.startswith("_")]
        source = "public_attrs"
    names = sorted(dict.fromkeys(names))[:20]
    return {
        "public_source": source,
        "public_names": names,
        "version_present": hasattr(module, "__version__"),
        "attr_kinds": {name: _attribute_kind(module, name) for name in names},
    }


def _attribute_kind(module: Any, name: str) -> str:
    try:
        return _value_kind(getattr(module, name, None))
    except Exception:
        return "unavailable"


def _value_kind(value: Any) -> str:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return type(value).__name__
    return type(value).__name__


def _static_shape_fallback(path: Path, entrypoint: str, module_name: str, exc: Exception) -> dict[str, Any]:
    reason = f"{type(exc).__name__}: {exc}"
    if path.name != "__init__.py" or not _static_shape_fallback_allowed(reason):
        return {}
    return {
        "status": "ok",
        "entrypoint": entrypoint,
        "module": module_name,
        "shape": static_module_shape(path),
        "dependency_stubs": list(getattr(exc, "dependency_stubs", []) or []) + ["static_shape_fallback"],
        "fallback_reason": reason,
    }


def _static_shape_fallback_allowed(reason: str) -> bool:
    lowered = reason.lower()
    return lowered.startswith("assertionerror") or "functionnamespace" in lowered


@contextmanager
def _path_front(*paths: Path):
    added = []
    for path in reversed(paths):
        value = str(path)
        sys.path.insert(0, value)
        added.append(value)
    try:
        yield
    finally:
        for value in added:
            try:
                sys.path.remove(value)
            except ValueError:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
