"""Small AST helpers shared by source contract inference."""

from __future__ import annotations

import ast


def local_type_factories(function: ast.AST) -> dict[str, str]:
    return {
        node.name: "TypeFactory"
        for node in getattr(function, "body", [])
        if isinstance(node, ast.ClassDef)
    }
