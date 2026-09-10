"""Static module shape fallback for import-hostile package initializers."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any


def static_module_shape(path: Path) -> dict[str, Any]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = _public_names(tree)
    return {
        "public_source": "static_ast_fallback",
        "public_names": names,
        "version_present": "__version__" in names,
        "attr_kinds": {name: _kind_for_name(tree, name) for name in names},
    }


def _public_names(tree: ast.Module) -> list[str]:
    exported = _literal_all(tree)
    if exported:
        return exported[:20]
    names: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.Assign):
            names.extend(_target_names(node.targets))
        elif isinstance(node, ast.AnnAssign):
            names.extend(_target_names([node.target]))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.append(node.name)
        elif isinstance(node, ast.Import):
            names.extend(alias.asname or alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            names.extend(alias.asname or alias.name for alias in node.names if alias.name != "*")
    return sorted({name for name in names if name == "__version__" or (name and not name.startswith("_"))})[:20]


def _literal_all(tree: ast.Module) -> list[str]:
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if "__all__" not in _target_names(node.targets):
            continue
        try:
            value = ast.literal_eval(node.value)
        except Exception:
            return []
        if isinstance(value, (list, tuple)):
            return [str(item) for item in value if isinstance(item, str)]
    return []


def _target_names(targets: list[ast.expr]) -> list[str]:
    names: list[str] = []
    for target in targets:
        if isinstance(target, ast.Name):
            names.append(target.id)
        elif isinstance(target, (ast.Tuple, ast.List)):
            names.extend(item.id for item in target.elts if isinstance(item, ast.Name))
    return names


def _kind_for_name(tree: ast.Module, name: str) -> str:
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == name:
            return "type"
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return "function"
        if isinstance(node, ast.Assign) and name in _target_names(node.targets):
            return _literal_kind(node.value)
        if isinstance(node, ast.AnnAssign) and name in _target_names([node.target]):
            return _literal_kind(node.value)
    return "module"


def _literal_kind(node: ast.AST | None) -> str:
    if isinstance(node, ast.Constant):
        return type(node.value).__name__
    if isinstance(node, ast.List):
        return "list"
    if isinstance(node, ast.Tuple):
        return "tuple"
    if isinstance(node, ast.Dict):
        return "dict"
    return "unknown"
