"""Select an unambiguous method owner from parsed source."""

from __future__ import annotations

import ast


def unique_method_class(tree: ast.Module, symbol: str) -> tuple[ast.ClassDef, set[str]] | None:
    owner, separator, method_name = symbol.partition(".")
    method_name = method_name if separator else owner
    matches: list[tuple[ast.ClassDef, set[str]]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef) or (separator and node.name != owner):
            continue
        method_names = {
            item.name
            for item in node.body
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        if method_name in method_names:
            matches.append((node, method_names))
    return matches[0] if len(matches) == 1 else None
