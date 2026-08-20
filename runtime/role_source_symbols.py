"""AST symbol matching for role source targets."""

from __future__ import annotations

import ast
from typing import Any


def symbol_matches(
    tree: ast.AST, symbol: str, owner_class: str | None = None
) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    parents = {
        child: parent
        for parent in ast.walk(tree)
        for child in ast.iter_child_nodes(parent)
    }
    for parent in ast.walk(tree):
        statement_lists = [
            value
            for _field, value in ast.iter_fields(parent)
            if isinstance(value, list) and any(isinstance(item, ast.stmt) for item in value)
        ]
        for node in [item for values in statement_lists for item in values]:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) or node.name != symbol:
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
            if owner_class and row.get("class_name") != owner_class:
                continue
            matches.append(row)
    return matches


def _enclosing_scopes(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> list[ast.AST]:
    scopes: list[ast.AST] = []
    parent = parents.get(node)
    while parent is not None:
        if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            scopes.append(parent)
        parent = parents.get(parent)
    return scopes
