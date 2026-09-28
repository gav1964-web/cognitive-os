"""AST symbol matching for role source targets."""

from __future__ import annotations

import ast
from functools import lru_cache
from typing import Any


def symbol_matches(
    tree: ast.AST, symbol: str, owner_class: str | None = None
) -> list[dict[str, Any]]:
    matches = [dict(row) for row in _symbol_index(tree).get(symbol, [])]
    if owner_class:
        matches = [row for row in matches if row.get("class_name") == owner_class]
    return matches


@lru_cache(maxsize=64)
def _symbol_index(tree: ast.AST) -> dict[str, list[dict[str, Any]]]:
    index: dict[str, list[dict[str, Any]]] = {}
    parents = {
        child: parent
        for parent in ast.walk(tree)
        for child in ast.iter_child_nodes(parent)
    }
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        row = {"kind": "function", "line": int(getattr(node, "lineno", 0) or 0)}
        scopes = _enclosing_scopes(node, parents)
        if scopes and isinstance(scopes[0], (ast.FunctionDef, ast.AsyncFunctionDef)):
            row.update({"kind": "nested_function", "parent_name": scopes[0].name})
        elif scopes and isinstance(scopes[0], ast.ClassDef):
            row.update({"kind": "method", "class_name": scopes[0].name})
            enclosing = next(
                (scope for scope in scopes[1:] if isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef))),
                None,
            )
            if enclosing:
                row.update({"kind": "nested_method", "parent_name": enclosing.name})
        index.setdefault(node.name, []).append(row)
    return index


def _enclosing_scopes(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> list[ast.AST]:
    scopes: list[ast.AST] = []
    parent = parents.get(node)
    while parent is not None:
        if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            scopes.append(parent)
        parent = parents.get(parent)
    return scopes
