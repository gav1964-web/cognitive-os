"""Source-isolated callable extraction for executable acceptance."""

from __future__ import annotations

import ast
import copy
from pathlib import Path
from typing import Any


def load_source_isolated_function(path: Path, symbol: str) -> dict[str, Any]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        functions = {
            node.name: node
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        if symbol not in functions:
            return {"callable": None, "reason": "target_not_callable"}
        names = _isolated_function_names(functions, symbol)
        imports = _needed_import_nodes(tree, names)
        nodes = [_strip_annotations(copy.deepcopy(functions[name])) for name in functions if name in names]
        module = ast.Module(body=[*imports, *nodes], type_ignores=[])
        ast.fix_missing_locations(module)
        namespace: dict[str, Any] = {}
        exec(compile(module, str(path), "exec"), namespace)
        func = namespace.get(symbol)
        return {"callable": func, "reason": "" if callable(func) else "target_not_callable"}
    except Exception as exc:
        return {"callable": None, "reason": _import_failure_reason(exc), "detail": _exception_detail(exc)}


def _isolated_function_names(functions: dict[str, ast.FunctionDef | ast.AsyncFunctionDef], symbol: str) -> set[str]:
    selected = {symbol}
    changed = True
    while changed:
        changed = False
        for name in list(selected):
            for loaded in _loaded_names(functions[name]):
                if loaded in functions and loaded not in selected:
                    selected.add(loaded)
                    changed = True
    return selected


def _needed_import_nodes(tree: ast.Module, selected_names: set[str]) -> list[ast.stmt]:
    loaded = {
        name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in selected_names
        for name in _loaded_names(node)
    }
    imports: list[ast.stmt] = []
    for node in tree.body:
        if isinstance(node, ast.Import) and _import_bound_names(node) & loaded:
            imports.append(copy.deepcopy(node))
        elif isinstance(node, ast.ImportFrom) and _import_bound_names(node) & loaded:
            imports.append(copy.deepcopy(node))
    return imports


def _loaded_names(node: ast.AST) -> set[str]:
    return {item.id for item in ast.walk(node) if isinstance(item, ast.Name) and isinstance(item.ctx, ast.Load)}


def _import_bound_names(node: ast.Import | ast.ImportFrom) -> set[str]:
    return {alias.asname or alias.name.split(".", 1)[0] for alias in node.names}


def _strip_annotations(func_node: ast.FunctionDef | ast.AsyncFunctionDef) -> ast.FunctionDef | ast.AsyncFunctionDef:
    func_node.decorator_list = []
    func_node.returns = None
    for arg in list(func_node.args.posonlyargs) + list(func_node.args.args) + list(func_node.args.kwonlyargs):
        arg.annotation = None
    if func_node.args.vararg:
        func_node.args.vararg.annotation = None
    if func_node.args.kwarg:
        func_node.args.kwarg.annotation = None
    return func_node


def _import_failure_reason(exc: Exception) -> str:
    if isinstance(exc, ModuleNotFoundError):
        return "import_failed_missing_module"
    if isinstance(exc, ImportError):
        return "import_failed_import_error"
    return "import_failed_runtime_error"


def _exception_detail(exc: Exception) -> str:
    name = getattr(exc, "name", "") or ""
    message = str(exc).splitlines()[0] if str(exc) else exc.__class__.__name__
    if name:
        return f"{name}: {message}"[:240]
    return message[:240]
