"""Infer bounded text-file fixtures from parser structure."""

from __future__ import annotations

import ast
from typing import Any


def add_delimited_file_samples(
    node: ast.AST,
    parameters: set[str],
    candidates: dict[str, list[tuple[int, Any, str]]],
    *,
    priority: int,
) -> None:
    opened = {
        call.args[0].id
        for call in ast.walk(node)
        if isinstance(call, ast.Call)
        and isinstance(call.func, ast.Name)
        and call.func.id == "open"
        and call.args
        and isinstance(call.args[0], ast.Name)
        and call.args[0].id in parameters
    }
    delimiter, columns = _delimited_unpack(node)
    if not delimiter or columns < 1:
        return
    for name in opened:
        candidates[name].append((priority, {
            "__fixture__": "delimited_text_path",
            "delimiter": delimiter,
            "columns": columns,
        }, "ast_delimited_text_path"))


def _delimited_unpack(node: ast.AST) -> tuple[str, int]:
    for item in ast.walk(node):
        if not isinstance(item, ast.Assign) or len(item.targets) != 1:
            continue
        target = item.targets[0]
        if not isinstance(target, (ast.Tuple, ast.List)):
            continue
        split = next((
            call for call in ast.walk(item.value)
            if isinstance(call, ast.Call)
            and isinstance(call.func, ast.Attribute)
            and call.func.attr in {"split", "rsplit"}
            and call.args
            and isinstance(call.args[0], ast.Constant)
            and isinstance(call.args[0].value, str)
        ), None)
        if split is not None:
            return str(split.args[0].value), len(target.elts)
    return "", 0
