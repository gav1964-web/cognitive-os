"""Infer bounded string and byte buffers from literal method predicates."""

from __future__ import annotations

import ast
from typing import Any

Candidates = dict[str, list[tuple[int, Any, str]]]
FunctionNode = ast.FunctionDef | ast.AsyncFunctionDef


def add_literal_buffer_samples(
    node: FunctionNode,
    parameters: set[str],
    candidates: Candidates,
    *,
    priority: int,
    methods: dict[str, str],
    minimum_length: int,
) -> None:
    """Add samples only when a parameter is tested against a literal buffer."""
    asserted_negations = {
        id(item.test.operand)
        for item in ast.walk(node)
        if isinstance(item, ast.Assert)
        and isinstance(item.test, ast.UnaryOp)
        and isinstance(item.test.op, ast.Not)
        and isinstance(item.test.operand, ast.Call)
    }
    for item in ast.walk(node):
        if not isinstance(item, ast.Call) or not item.args:
            continue
        if not isinstance(item.func, ast.Attribute):
            continue
        receiver = item.func.value
        if not isinstance(receiver, ast.Name) or receiver.id not in parameters:
            continue
        position = methods.get(item.func.attr)
        literal = _literal_buffer(item.args[0])
        if position not in {"prefix", "suffix"} or literal is None:
            continue
        negated = id(item) in asserted_negations
        value = _nonmatching_sample(literal, minimum_length) if negated else _sample(literal, position, minimum_length)
        candidates[receiver.id].append(
            (
                priority,
                value,
                f"ast_literal_buffer:{'assert_not_' if negated else ''}{item.func.attr}",
            )
        )


def _literal_buffer(node: ast.AST) -> str | bytes | None:
    try:
        value = ast.literal_eval(node)
    except (ValueError, TypeError):
        return None
    return value if isinstance(value, (str, bytes)) and value else None


def _sample(literal: str | bytes, position: str, minimum_length: int) -> Any:
    size = max(len(literal), minimum_length)
    padding_size = size - len(literal)
    padding = b"\0" * padding_size if isinstance(literal, bytes) else "0" * padding_size
    value = literal + padding if position == "prefix" else padding + literal
    if isinstance(value, bytes):
        return {"__fixture__": "bytes_literal", "hex": value.hex()}
    return value


def _nonmatching_sample(literal: str | bytes, minimum_length: int) -> Any:
    size = max(1, minimum_length)
    padding = b"0" * size if isinstance(literal, bytes) else "0" * size
    if isinstance(padding, bytes):
        return {"__fixture__": "bytes_literal", "hex": padding.hex()}
    return padding
