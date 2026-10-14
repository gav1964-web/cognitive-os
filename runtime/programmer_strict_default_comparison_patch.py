"""Bounded AST-token edit for strict non-string CLI defaults."""

from __future__ import annotations

import ast
from typing import Any


def strict_default_comparison_patch(
    source: str, *, symbol: str, recipe: dict[str, Any]
) -> dict[str, Any] | None:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    function = _qualified_function(tree, symbol)
    required_suffix = str(recipe.get("required_symbol_suffix") or "")
    value_name = str(recipe.get("value_name") or "")
    if function is None or not symbol.endswith(required_suffix) or not value_name:
        return None
    if any(
        isinstance(node, ast.Name) and node.id == "isinstance" and isinstance(node.ctx, ast.Store)
        for node in ast.walk(function)
    ):
        return None
    candidates = [
        node for node in ast.walk(function) if _empty_string_comparison(node, value_name)
    ]
    if len(candidates) != 1:
        return None
    comparison = candidates[0]
    assert isinstance(comparison, ast.Compare)
    start = _offset(source, int(comparison.lineno), int(comparison.col_offset))
    end = _offset(source, int(comparison.end_lineno), int(comparison.end_col_offset))
    original = source[start:end]
    patched = source[:start] + f"isinstance({value_name}, str) and {original}" + source[end:]
    try:
        ast.parse(patched)
    except SyntaxError:
        return None
    return {"source": patched, "value_name": value_name}


def _empty_string_comparison(node: ast.AST, value_name: str) -> bool:
    return (
        isinstance(node, ast.Compare)
        and isinstance(node.left, ast.Name)
        and node.left.id == value_name
        and len(node.ops) == 1
        and isinstance(node.ops[0], ast.Eq)
        and len(node.comparators) == 1
        and isinstance(node.comparators[0], ast.Constant)
        and node.comparators[0].value == ""
    )


def _qualified_function(
    tree: ast.Module, symbol: str
) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    parts = symbol.split(".")
    body: list[ast.stmt] = tree.body
    selected: ast.AST | None = None
    for index, part in enumerate(parts):
        allowed = (ast.ClassDef,) if index < len(parts) - 1 else (ast.FunctionDef, ast.AsyncFunctionDef)
        selected = next((node for node in body if isinstance(node, allowed) and node.name == part), None)
        if selected is None:
            return None
        body = list(getattr(selected, "body", []))
    return selected if isinstance(selected, (ast.FunctionDef, ast.AsyncFunctionDef)) else None


def _offset(source: str, line: int, column: int) -> int:
    lines = source.splitlines(keepends=True)
    return sum(len(value) for value in lines[: line - 1]) + column
