"""Classify callable target shape without importing project code."""

from __future__ import annotations

import ast
from pathlib import Path


def ast_skip_reason(path: Path, symbol: str) -> str:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except Exception:
        return "target_not_callable"
    top_level = any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == symbol
        for node in tree.body
    )
    if top_level:
        return "target_not_callable"
    class_matches = [
        item
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef)
        for item in node.body
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == symbol
    ]
    if len(class_matches) == 1:
        return "method_target_needs_instance_fixture"
    nested_matches = [
        item
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        for item in ast.walk(node)
        if item is not node and isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == symbol
    ]
    if len(nested_matches) == 1:
        return "nested_function_requires_closure"
    if len(class_matches) + len(nested_matches) > 1:
        return "ambiguous_nested_callable_target"
    return "target_not_callable"
