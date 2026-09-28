"""Bounded AST edit for a cross-platform timestamp range error contract."""

from __future__ import annotations

import ast
from typing import Any


def timestamp_range_error_patch(
    source: str, *, symbol: str, recipe: dict[str, Any]
) -> dict[str, Any] | None:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    function = next(
        (node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == symbol),
        None,
    )
    required = {str(value) for value in recipe.get("required_exceptions") or [] if value}
    raised = str(recipe.get("raised_exception") or "")
    message = str(recipe.get("replacement_message") or "")
    if function is None or len(required) != 2 or not raised or not message:
        return None
    handlers: dict[str, ast.ExceptHandler] = {}
    for node in ast.walk(function):
        if not isinstance(node, ast.ExceptHandler) or not isinstance(node.type, ast.Name):
            continue
        if node.type.id in required:
            if node.type.id in handlers:
                return None
            handlers[node.type.id] = node
    if set(handlers) != required:
        return None
    if any(
        len(handler.body) != 1 or not _literal_value_error_raise(handler.body[0], raised)
        for handler in handlers.values()
    ):
        return None
    clone = ast.parse(ast.unparse(function)).body[0]
    assert isinstance(clone, ast.FunctionDef)
    changed = []
    for node in ast.walk(clone):
        if not isinstance(node, ast.ExceptHandler) or not isinstance(node.type, ast.Name):
            continue
        if node.type.id not in required:
            continue
        statement = node.body[0]
        assert isinstance(statement, ast.Raise) and isinstance(statement.exc, ast.Call)
        statement.exc.args[0] = ast.Constant(value=message)
        changed.append(node.type.id)
    if set(changed) != required:
        return None
    replacement = ast.unparse(ast.fix_missing_locations(clone))
    lines = source.splitlines(keepends=True)
    start = int(function.lineno) - 1
    end = int(getattr(function, "end_lineno", function.lineno))
    newline = "\r\n" if "\r\n" in source else "\n"
    patched = "".join(lines[:start]) + replacement.replace("\n", newline) + newline + "".join(lines[end:])
    try:
        ast.parse(patched)
    except SyntaxError:
        return None
    return {"source": patched, "exceptions": sorted(changed), "message": message}


def _literal_value_error_raise(statement: ast.stmt, raised: str) -> bool:
    return (
        isinstance(statement, ast.Raise)
        and isinstance(statement.exc, ast.Call)
        and isinstance(statement.exc.func, ast.Name)
        and statement.exc.func.id == raised
        and len(statement.exc.args) == 1
        and isinstance(statement.exc.args[0], ast.Constant)
        and isinstance(statement.exc.args[0].value, str)
    )
