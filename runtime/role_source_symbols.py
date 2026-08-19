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
            if isinstance(parent, ast.ClassDef):
                row.update({"kind": "method", "class_name": parent.name})
                enclosing = _enclosing_function(parent, parents)
                if enclosing:
                    row.update({"kind": "nested_method", "parent_name": enclosing})
            elif isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef)):
                row.update({"kind": "nested_function", "parent_name": parent.name})
            if owner_class and row.get("class_name") != owner_class:
                continue
            matches.append(row)
    return matches


def _enclosing_function(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> str:
    parent = parents.get(node)
    while parent is not None:
        if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return parent.name
        parent = parents.get(parent)
    return ""
