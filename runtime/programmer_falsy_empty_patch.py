"""Bounded AST edit for falsy primitive versus empty-value contracts."""

from __future__ import annotations

import ast
from typing import Any


def falsy_primitive_empty_patch(
    source: str, *, symbol: str, recipe: dict[str, Any]
) -> dict[str, Any] | None:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    function = _qualified_function(tree, symbol)
    if function is None or not symbol.endswith(str(recipe.get("required_symbol_suffix") or "")):
        return None
    statements = list(function.body)
    if statements and _is_docstring(statements[0]):
        statements = statements[1:]
    if len(statements) != 1 or not isinstance(statements[0], ast.Return):
        return None
    expression = statements[0].value
    if not isinstance(expression, ast.IfExp):
        return None
    if not all(isinstance(node, ast.Name) for node in (expression.test, expression.body, expression.orelse)):
        return None
    assert isinstance(expression.test, ast.Name)
    assert isinstance(expression.body, ast.Name)
    assert isinstance(expression.orelse, ast.Name)
    if expression.test.id != expression.body.id or expression.test.id == expression.orelse.id:
        return None
    parameters = {
        arg.arg for arg in [*function.args.posonlyargs, *function.args.args, *function.args.kwonlyargs]
    }
    candidate = expression.test.id
    fallback = expression.orelse.id
    if candidate not in parameters or fallback not in parameters:
        return None

    clone = ast.parse(ast.unparse(function)).body[0]
    assert isinstance(clone, (ast.FunctionDef, ast.AsyncFunctionDef))
    retained = clone.body[:1] if clone.body and _is_docstring(clone.body[0]) else []
    replacement = ast.parse(
        f"if {candidate} is None:\n"
        f"    return {fallback}\n"
        f"if hasattr({candidate}, '__len__') and len({candidate}) == 0:\n"
        f"    return {fallback}\n"
        f"return {candidate}\n"
    ).body
    clone.body = [*retained, *replacement]
    rendered = ast.unparse(ast.fix_missing_locations(clone))
    lines = source.splitlines(keepends=True)
    decorated_lines = [int(node.lineno) for node in function.decorator_list]
    start = min([int(function.lineno), *decorated_lines]) - 1
    end = int(getattr(function, "end_lineno", function.lineno))
    newline = "\r\n" if "\r\n" in source else "\n"
    indent = " " * int(function.col_offset)
    indented = newline.join(indent + line if line else line for line in rendered.splitlines())
    patched = "".join(lines[:start]) + indented + newline + "".join(lines[end:])
    try:
        ast.parse(patched)
    except SyntaxError:
        return None
    return {
        "source": patched,
        "candidate_parameter": candidate,
        "fallback_parameter": fallback,
    }


def _qualified_function(tree: ast.Module, symbol: str) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
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


def _is_docstring(statement: ast.stmt) -> bool:
    return (
        isinstance(statement, ast.Expr)
        and isinstance(statement.value, ast.Constant)
        and isinstance(statement.value.value, str)
    )
