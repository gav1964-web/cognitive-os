"""Bounded AST-token edit for a proven duplicate Click short option."""

from __future__ import annotations

import ast
from typing import Any


def duplicate_cli_option_patch(
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
    if function is None or symbol != str(recipe.get("required_symbol") or ""):
        return None
    option_to_change = str(recipe.get("option_to_change") or "")
    peer_option = str(recipe.get("peer_option") or "")
    duplicate_flag = str(recipe.get("duplicate_short_flag") or "")
    replacement_flag = str(recipe.get("replacement_short_flag") or "")
    if not all((option_to_change, peer_option, duplicate_flag, replacement_flag)):
        return None

    options = [_click_option(decorator) for decorator in function.decorator_list]
    options = [option for option in options if option is not None]
    if any(replacement_flag in values for _, values in options):
        return None
    selected = [
        (call, values)
        for call, values in options
        if option_to_change in values and duplicate_flag in values
    ]
    peers = [
        (call, values)
        for call, values in options
        if peer_option in values and duplicate_flag in values
    ]
    duplicate_owners = [values for _, values in options if duplicate_flag in values]
    if len(selected) != 1 or len(peers) != 1 or len(duplicate_owners) != 2:
        return None
    call, _ = selected[0]
    short_arg = next(
        (arg for arg in call.args if isinstance(arg, ast.Constant) and arg.value == duplicate_flag),
        None,
    )
    if not isinstance(short_arg, ast.Constant):
        return None
    start = _offset(source, int(short_arg.lineno), int(short_arg.col_offset))
    end = _offset(source, int(short_arg.end_lineno), int(short_arg.end_col_offset))
    patched = source[:start] + repr(replacement_flag) + source[end:]
    try:
        ast.parse(patched)
    except SyntaxError:
        return None
    return {
        "source": patched,
        "option": option_to_change,
        "old_short_flag": duplicate_flag,
        "new_short_flag": replacement_flag,
    }


def _click_option(node: ast.expr) -> tuple[ast.Call, tuple[str, ...]] | None:
    if not (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "click"
        and node.func.attr == "option"
        and all(isinstance(arg, ast.Constant) and isinstance(arg.value, str) for arg in node.args)
    ):
        return None
    return node, tuple(str(arg.value) for arg in node.args if isinstance(arg, ast.Constant))


def _offset(source: str, line: int, column: int) -> int:
    lines = source.splitlines(keepends=True)
    return sum(len(value) for value in lines[: line - 1]) + column
