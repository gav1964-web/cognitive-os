"""Bounded AST edit for escaped-brace offsets in Python 3.12 f-strings."""

from __future__ import annotations

import ast
from typing import Any


def fstring_brace_offset_patch(
    source: str, *, symbol: str, recipe: dict[str, Any]
) -> dict[str, Any] | None:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    if symbol != str(recipe.get("required_symbol") or ""):
        return None
    function = _qualified_function(tree, symbol)
    if function is None:
        return None
    offset_name = str(recipe.get("offset_name") or "brace_offset")
    if offset_name in {node.id for node in ast.walk(function) if isinstance(node, ast.Name)}:
        return None
    branches = [node for node in ast.walk(function) if isinstance(node, ast.If) and _fstring_middle_test(node.test)]
    if len(branches) != 1 or len(branches[0].body) != 1:
        return None
    assignment = branches[0].body[0]
    if not _legacy_middle_assignment(assignment) or assignment.lineno != assignment.end_lineno:
        return None
    if not _has_token_loop(function):
        return None

    lines = source.splitlines(keepends=True)
    line_index = int(assignment.lineno) - 1
    newline = "\r\n" if lines[line_index].endswith("\r\n") else "\n"
    indent = lines[line_index][: int(assignment.col_offset)]
    replacement = (
        f'{indent}{offset_name} = text.count("{{") + text.count("}}"){newline}'
        f'{indent}text = "x" * (len(text) + {offset_name}){newline}'
        f'{indent}end = (end[0], end[1] + {offset_name}){newline}'
    )
    patched = "".join(lines[:line_index]) + replacement + "".join(lines[line_index + 1 :])
    try:
        ast.parse(patched)
    except SyntaxError:
        return None
    return {"source": patched, "offset_name": offset_name}


def _qualified_function(tree: ast.Module, symbol: str) -> ast.FunctionDef | None:
    current: list[ast.stmt] = list(tree.body)
    found: ast.AST | None = None
    for part in symbol.split("."):
        found = next(
            (
                node for node in current
                if isinstance(node, (ast.ClassDef, ast.FunctionDef)) and node.name == part
            ),
            None,
        )
        if found is None:
            return None
        current = list(found.body) if isinstance(found, (ast.ClassDef, ast.FunctionDef)) else []
    return found if isinstance(found, ast.FunctionDef) else None


def _fstring_middle_test(node: ast.expr) -> bool:
    return (
        isinstance(node, ast.Compare)
        and isinstance(node.left, ast.Name)
        and node.left.id == "token_type"
        and len(node.ops) == 1
        and isinstance(node.ops[0], ast.Eq)
        and len(node.comparators) == 1
        and isinstance(node.comparators[0], ast.Name)
        and node.comparators[0].id == "FSTRING_MIDDLE"
    )


def _legacy_middle_assignment(node: ast.stmt) -> bool:
    if not (
        isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id == "text"
        and isinstance(node.value, ast.BinOp)
        and isinstance(node.value.op, ast.Mult)
        and isinstance(node.value.left, ast.Constant)
        and node.value.left.value == "x"
        and isinstance(node.value.right, ast.Call)
        and isinstance(node.value.right.func, ast.Name)
        and node.value.right.func.id == "len"
        and len(node.value.right.args) == 1
        and isinstance(node.value.right.args[0], ast.Name)
        and node.value.right.args[0].id == "text"
        and not node.value.right.keywords
    ):
        return False
    return True


def _has_token_loop(function: ast.FunctionDef) -> bool:
    return any(
        isinstance(node, ast.For)
        and isinstance(node.target, (ast.Tuple, ast.List))
        and [item.id for item in node.target.elts if isinstance(item, ast.Name)]
        == ["token_type", "text", "start", "end", "line"]
        and isinstance(node.iter, ast.Attribute)
        and isinstance(node.iter.value, ast.Name)
        and node.iter.value.id == "self"
        and node.iter.attr == "tokens"
        for node in ast.walk(function)
    )
