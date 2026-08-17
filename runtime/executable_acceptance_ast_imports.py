"""Select imports required by a source-isolated callable."""

from __future__ import annotations

import ast
import copy


def needed_import_nodes(tree: ast.Module, nodes: list[ast.AST]) -> list[ast.stmt]:
    loaded = {name for node in nodes for name in loaded_names(node)}
    imports: list[ast.stmt] = []
    for node in _module_scope_nodes(tree.body):
        if isinstance(node, (ast.Import, ast.ImportFrom)) and _bound_names(node) & loaded:
            imports.append(copy.deepcopy(node))
    return imports


def loaded_names(node: ast.AST) -> set[str]:
    return {
        item.id
        for item in ast.walk(node)
        if isinstance(item, ast.Name) and isinstance(item.ctx, ast.Load)
    }


def _module_scope_nodes(nodes: list[ast.stmt]):
    for node in nodes:
        yield node
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        for field in ("body", "orelse", "finalbody"):
            children = getattr(node, field, None)
            if isinstance(children, list):
                yield from _module_scope_nodes(children)
        for handler in getattr(node, "handlers", []):
            yield from _module_scope_nodes(handler.body)


def _bound_names(node: ast.Import | ast.ImportFrom) -> set[str]:
    return {alias.asname or alias.name.split(".", 1)[0] for alias in node.names}
