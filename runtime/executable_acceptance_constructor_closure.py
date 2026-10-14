"""Detect constructors that a source-isolated class method must retain."""

from __future__ import annotations

import ast


FunctionNode = ast.FunctionDef | ast.AsyncFunctionDef


def constructs_owner(
    methods: dict[str, FunctionNode], selected: set[str], class_name: str
) -> bool:
    constructors = {"cls", class_name}
    return any(
        isinstance(item, ast.Call)
        and isinstance(item.func, ast.Name)
        and item.func.id in constructors
        for name in selected
        for item in ast.walk(methods[name])
    )
