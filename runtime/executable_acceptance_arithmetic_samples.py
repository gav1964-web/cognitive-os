"""Infer numeric acceptance samples without misclassifying concatenation."""

from __future__ import annotations

import ast
from typing import Any

from .source_expression_shapes import expression_shape

Candidates = dict[str, list[tuple[int, Any, str]]]


def add_numeric_arithmetic_sample(
    node: ast.AST,
    parameters: set[str],
    candidates: Candidates,
    assignments: dict[str, str],
    *,
    priority: int,
    sample: Any,
) -> None:
    if not isinstance(node, ast.BinOp):
        return
    if isinstance(node.op, ast.Mod) and any(
        isinstance(_literal(value), str) for value in (node.left, node.right)
    ):
        return
    if expression_shape(node, assignments) in {
        "str", "bytes", "SequenceLike", "StringSequenceLike", "TupleLike",
    }:
        return
    for expression in (node.left, node.right):
        if isinstance(expression, ast.Name) and expression.id in parameters:
            candidates[expression.id].append((priority, sample, "ast_numeric_arithmetic"))


def _literal(node: ast.AST) -> Any:
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError):
        return None
