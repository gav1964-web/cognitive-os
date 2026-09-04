"""Bounded loop guard for an input ending with a continuation backslash."""

from __future__ import annotations

import ast
from typing import Any


def trailing_backslash_bounds_patch(
    source: str, *, symbol: str, recipe: dict[str, Any]
) -> dict[str, Any] | None:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    if symbol != str(recipe.get("required_symbol") or ""):
        return None
    function = next(
        (node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == symbol),
        None,
    )
    if function is None:
        return None
    index_name = str(recipe.get("index_name") or "index")
    count_name = str(recipe.get("count_name") or "line_count")
    loops = [
        node for node in ast.walk(function)
        if isinstance(node, ast.While) and _legacy_backslash_test(node.test)
    ]
    if len(loops) != 1 or not _bounded_body(loops[0], index_name=index_name):
        return None
    names = {node.id for node in ast.walk(function) if isinstance(node, ast.Name)}
    if index_name not in names or count_name not in names:
        return None
    loop = loops[0]
    if loop.lineno != loop.test.end_lineno:
        return None

    lines = source.splitlines(keepends=True)
    line_index = int(loop.lineno) - 1
    line = lines[line_index]
    newline = "\r\n" if line.endswith("\r\n") else "\n" if line.endswith("\n") else ""
    content = line[: -len(newline)] if newline else line
    expected = 'while line.strip().endswith("\\\\"):'
    if content.strip() != expected:
        return None
    indent = content[: len(content) - len(content.lstrip())]
    lines[line_index] = (
        f'{indent}while line.strip().endswith("\\\\") and {index_name} < {count_name}:{newline}'
    )
    patched = "".join(lines)
    try:
        ast.parse(patched)
    except SyntaxError:
        return None
    return {"source": patched, "index_name": index_name, "count_name": count_name}


def _legacy_backslash_test(node: ast.expr) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "endswith"
        and len(node.args) == 1
        and isinstance(node.args[0], ast.Constant)
        and node.args[0].value == "\\"
        and not node.keywords
        and isinstance(node.func.value, ast.Call)
        and isinstance(node.func.value.func, ast.Attribute)
        and node.func.value.func.attr == "strip"
        and not node.func.value.args
        and not node.func.value.keywords
        and isinstance(node.func.value.func.value, ast.Name)
        and node.func.value.func.value.id == "line"
    )


def _bounded_body(loop: ast.While, *, index_name: str) -> bool:
    reads_index = any(
        isinstance(node, ast.Subscript)
        and isinstance(node.value, ast.Name)
        and node.value.id == "in_lines"
        and isinstance(node.slice, ast.Name)
        and node.slice.id == index_name
        for statement in loop.body
        for node in ast.walk(statement)
    )
    increments_index = any(
        isinstance(node, ast.AugAssign)
        and isinstance(node.target, ast.Name)
        and node.target.id == index_name
        and isinstance(node.op, ast.Add)
        and isinstance(node.value, ast.Constant)
        and node.value.value == 1
        for statement in loop.body
        for node in ast.walk(statement)
    )
    return reads_index and increments_index
