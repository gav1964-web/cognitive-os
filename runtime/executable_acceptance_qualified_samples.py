"""Infer argument fixtures from exact qualified-call contracts."""

from __future__ import annotations

import ast
from typing import Any

Candidates = dict[str, list[tuple[int, Any, str]]]
FunctionNode = ast.FunctionDef | ast.AsyncFunctionDef


def add_qualified_call_samples(
    node: FunctionNode,
    parameters: set[str],
    candidates: Candidates,
    *,
    priority: int,
    samples: dict[str, Any],
) -> None:
    for item in ast.walk(node):
        if not isinstance(item, ast.Call) or not item.args:
            continue
        qualified = _qualified_name(item.func)
        sample = samples.get(qualified)
        argument = item.args[0]
        if sample is None or not isinstance(argument, ast.Name):
            continue
        if argument.id in parameters:
            candidates[argument.id].append(
                (priority, sample, f"ast_qualified_call:{qualified}")
            )


def _qualified_name(node: ast.AST) -> str:
    if not isinstance(node, ast.Attribute) or not isinstance(node.value, ast.Name):
        return ""
    return f"{node.value.id}.{node.attr}"
