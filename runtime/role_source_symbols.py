"""AST symbol matching for role source targets."""

from __future__ import annotations

import ast
from typing import Any


def symbol_matches(
    tree: ast.AST, symbol: str, owner_class: str | None = None
) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    for parent in ast.walk(tree):
        body = getattr(parent, "body", None)
        if not isinstance(body, list):
            continue
        for node in body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) or node.name != symbol:
                continue
            row = {"kind": "function", "line": int(getattr(node, "lineno", 0) or 0)}
            if isinstance(parent, ast.ClassDef):
                row.update({"kind": "method", "class_name": parent.name})
            elif isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef)):
                row.update({"kind": "nested_function", "parent_name": parent.name})
            if owner_class and row.get("class_name") != owner_class:
                continue
            matches.append(row)
    return matches
