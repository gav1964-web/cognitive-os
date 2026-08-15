"""Static, non-importing dependency readiness for a Python source module."""

from __future__ import annotations

import ast
import importlib.util
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

from .python_parser_compatibility import parse_compatible_source
from .technical_spec_policy import load_technical_spec_policy


def source_dependency_readiness(project_root: Path, relative_path: str) -> dict[str, Any]:
    policy = dict(load_technical_spec_policy().get("dependency_readiness") or {})
    if not policy.get("enabled", True):
        return {"status": "disabled", "missing_external_modules": []}
    return _readiness(
        str(project_root.resolve()),
        str(relative_path).replace("\\", "/"),
        int(policy.get("max_local_import_depth") or 0),
    )


@lru_cache(maxsize=4096)
def _readiness(root_text: str, relative_path: str, max_depth: int) -> dict[str, Any]:
    root = Path(root_text)
    start = (root / relative_path).resolve()
    external: set[str] = set()
    local_modules: set[str] = set()
    visited: set[Path] = set()
    _walk_imports(root, start, max_depth, visited, local_modules, external)
    missing = sorted(module for module in external if not _module_available(module))
    return {
        "status": "missing_external" if missing else "ready",
        "module": relative_path,
        "local_modules_scanned": len(visited),
        "local_imports": sorted(local_modules)[:24],
        "external_imports": sorted(external)[:24],
        "missing_external_modules": missing[:12],
        "analysis": "static_import_graph_no_project_import",
    }


def _walk_imports(
    root: Path,
    path: Path,
    depth: int,
    visited: set[Path],
    local_modules: set[str],
    external: set[str],
) -> None:
    if depth < 0 or path in visited or not path.is_file():
        return
    visited.add(path)
    try:
        tree, _ = parse_compatible_source(path.read_text(encoding="utf-8", errors="replace"), path.as_posix())
    except (OSError, SyntaxError):
        return
    for module in _imported_modules(tree, root, path):
        local_path = _local_module_path(root, module)
        if local_path is not None:
            local_modules.add(module)
            _walk_imports(root, local_path, depth - 1, visited, local_modules, external)
            continue
        root_module = module.split(".", 1)[0]
        if root_module and root_module not in sys.stdlib_module_names:
            external.add(root_module)


def _imported_modules(tree: ast.AST, root: Path, path: Path) -> list[str]:
    modules: list[str] = []
    package = _package_parts(root, path)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = _absolute_from_import(package, int(node.level or 0), str(node.module or ""))
            if module:
                modules.append(module)
    return modules


def _package_parts(root: Path, path: Path) -> list[str]:
    try:
        relative = path.relative_to(root)
    except ValueError:
        return []
    parts = list(relative.with_suffix("").parts)
    return parts[:-1] if parts and parts[-1] != "__init__" else parts[:-1]


def _absolute_from_import(package: list[str], level: int, module: str) -> str:
    if level <= 0:
        return module
    keep = max(0, len(package) - level + 1)
    return ".".join([*package[:keep], *([module] if module else [])])


def _local_module_path(root: Path, module: str) -> Path | None:
    if not module:
        return None
    for source_root in (root, root / "src"):
        base = source_root.joinpath(*module.split("."))
        module_file = base.with_suffix(".py")
        package_file = base / "__init__.py"
        if module_file.is_file():
            return module_file.resolve()
        if package_file.is_file():
            return package_file.resolve()
    return None


@lru_cache(maxsize=1024)
def _module_available(module: str) -> bool:
    try:
        return importlib.util.find_spec(module) is not None
    except (ImportError, ModuleNotFoundError, ValueError):
        return False
