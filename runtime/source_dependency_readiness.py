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


def source_dependency_readiness(
    project_root: Path, relative_path: str, symbol: str | None = None
) -> dict[str, Any]:
    policy = dict(load_technical_spec_policy().get("dependency_readiness") or {})
    if not policy.get("enabled", True):
        return {"status": "disabled", "missing_external_modules": []}
    return _readiness(
        str(project_root.resolve()),
        str(relative_path).replace("\\", "/"),
        int(policy.get("max_local_import_depth") or 0),
        str(symbol or ""),
    )


@lru_cache(maxsize=4096)
def _readiness(root_text: str, relative_path: str, max_depth: int, symbol: str = "") -> dict[str, Any]:
    root = Path(root_text)
    start = (root / relative_path).resolve()
    external: set[str] = set()
    local_modules: set[str] = set()
    visited: set[Path] = set()
    if symbol:
        _walk_symbol_imports(root, start, symbol, max_depth, visited, local_modules, external)
    else:
        _walk_imports(root, start, max_depth, visited, local_modules, external)
    policy = dict(load_technical_spec_policy().get("dependency_readiness") or {})
    compat_stdlib = {str(item) for item in policy.get("stdlib_compat_modules", [])}
    missing = sorted(module for module in external if module not in compat_stdlib and not _module_available(module))
    return {
        "status": "missing_external" if missing else "ready",
        "module": relative_path,
        "local_modules_scanned": len(visited),
        "local_imports": sorted(local_modules)[:24],
        "external_imports": sorted(external)[:24],
        "missing_external_modules": missing[:12],
        "analysis": "function_scoped_static_import_graph" if symbol else "static_import_graph_no_project_import",
    }


def _walk_symbol_imports(
    root: Path, path: Path, symbol: str, depth: int, visited: set[Path],
    local_modules: set[str], external: set[str],
) -> None:
    if not path.is_file():
        return
    visited.add(path)
    try:
        tree, _ = parse_compatible_source(path.read_text(encoding="utf-8", errors="replace"), path.as_posix())
    except (OSError, SyntaxError):
        return
    modules = _modules_used_by_symbol(tree, symbol)
    if modules is None:
        _walk_imports(root, path, depth, visited, local_modules, external)
        return
    for module in modules:
        local_path = _local_module_path(root, module)
        if local_path is not None:
            local_modules.add(module)
            _walk_imports(root, local_path, depth - 1, visited, local_modules, external)
            continue
        root_module = module.split(".", 1)[0]
        if root_module and root_module not in sys.stdlib_module_names:
            external.add(root_module)


def _modules_used_by_symbol(tree: ast.Module, symbol: str) -> set[str] | None:
    imports: dict[str, str] = {}
    wildcard_modules: set[str] = set()
    definitions = {
        node.name: node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    for node in tree.body:
        if isinstance(node, ast.Import):
            imports.update({alias.asname or alias.name.split(".", 1)[0]: alias.name for alias in node.names})
        elif isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                if alias.name == "*":
                    wildcard_modules.add(node.module)
                else:
                    imports[alias.asname or alias.name] = node.module
    start = definitions.get(symbol.rsplit(".", 1)[-1])
    if start is None:
        return None
    selected: list[ast.AST] = []
    queue = [start]
    seen = set()
    while queue:
        node = queue.pop()
        if id(node) in seen:
            continue
        seen.add(id(node))
        selected.append(node)
        called = {
            child.func.id for child in ast.walk(node)
            if isinstance(child, ast.Call) and isinstance(child.func, ast.Name)
        }
        queue.extend(definitions[name] for name in called if name in definitions)
    loaded = {
        child.id for node in selected for child in ast.walk(node)
        if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load)
    }
    scoped_imports = {
        alias.name
        for node in selected for child in ast.walk(node)
        if isinstance(child, ast.Import)
        for alias in child.names
    }
    scoped_imports.update(
        child.module
        for node in selected for child in ast.walk(node)
        if isinstance(child, ast.ImportFrom) and not child.level and child.module
    )
    return {module for name, module in imports.items() if name in loaded} | wildcard_modules | scoped_imports


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

    class RuntimeImportVisitor(ast.NodeVisitor):
        def visit_If(self, node: ast.If) -> None:
            if _is_type_checking_test(node.test):
                for child in node.orelse:
                    self.visit(child)
                return
            self.generic_visit(node)

        def visit_Import(self, node: ast.Import) -> None:
            modules.extend(alias.name for alias in node.names)

        def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
            module = _absolute_from_import(package, int(node.level or 0), str(node.module or ""))
            if module:
                modules.append(module)

    RuntimeImportVisitor().visit(tree)
    return modules


def _is_type_checking_test(node: ast.AST) -> bool:
    return bool(
        isinstance(node, ast.Name) and node.id == "TYPE_CHECKING"
        or isinstance(node, ast.Attribute)
        and node.attr == "TYPE_CHECKING"
        and isinstance(node.value, ast.Name)
        and node.value.id == "typing"
    )


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
    for source_root in _local_source_roots(root):
        base = source_root.joinpath(*module.split("."))
        module_file = base.with_suffix(".py")
        package_file = base / "__init__.py"
        if module_file.is_file():
            return module_file.resolve()
        if package_file.is_file():
            return package_file.resolve()
        if base.is_dir() and any(base.rglob("*.py")):
            return base.resolve()
    return None


@lru_cache(maxsize=256)
def _local_source_roots(root: Path) -> tuple[Path, ...]:
    roots = [root, root / "src"]
    manifest_names = ("pyproject.toml", "setup.cfg", "setup.py")
    try:
        children = [child for child in root.iterdir() if child.is_dir()]
    except OSError:
        children = []
    for child in children:
        if any((child / name).is_file() for name in manifest_names):
            roots.extend((child, child / "src"))
    return tuple(dict.fromkeys(roots))


@lru_cache(maxsize=1024)
def _module_available(module: str) -> bool:
    try:
        return importlib.util.find_spec(module) is not None
    except (ImportError, ModuleNotFoundError, ValueError):
        return False
