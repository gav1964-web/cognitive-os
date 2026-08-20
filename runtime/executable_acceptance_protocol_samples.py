"""Safe protocol fixtures inferred from calls on function parameters."""

from __future__ import annotations

import ast
from typing import Any


def add_iterated_literal_domain_samples(
    node: ast.AST,
    parameters: set[str],
    candidates: dict[str, list[tuple[int, Any, str]]],
    *,
    priority: int,
) -> None:
    for loop in (item for item in ast.walk(node) if isinstance(item, ast.For)):
        if not isinstance(loop.target, ast.Name) or not isinstance(loop.iter, ast.Name):
            continue
        if loop.iter.id not in parameters:
            continue
        literal = next((
            other.value
            for comparison in ast.walk(loop)
            if isinstance(comparison, ast.Compare)
            for other in [comparison.left, *comparison.comparators]
            if isinstance(other, ast.Constant)
            and isinstance(other.value, (str, int, float, bool))
            and any(isinstance(part, ast.Name) and part.id == loop.target.id for part in [comparison.left, *comparison.comparators])
        ), None)
        if literal is not None:
            candidates[loop.iter.id].append((priority, [literal], "ast_iterated_literal_domain"))


def add_parameter_method_samples(
    node: ast.AST,
    parameters: set[str],
    candidates: dict[str, list[tuple[int, Any, str]]],
    *,
    priority: int,
    prefixes: tuple[str, ...],
) -> None:
    methods: dict[str, set[str]] = {name: set() for name in parameters}
    for item in ast.walk(node):
        if not isinstance(item, ast.Call) or not isinstance(item.func, ast.Attribute):
            continue
        owner = item.func.value
        if (
            isinstance(owner, ast.Name)
            and owner.id in parameters
            and item.func.attr.startswith(prefixes)
        ):
            methods[owner.id].add(item.func.attr)
    for name, called in methods.items():
        if called:
            candidates[name].append((priority, {
                "__fixture__": "declared_model",
                "type": "AcceptanceProtocol",
                "fields": {
                    method: {"__fixture__": "callable_empty_list"}
                    for method in sorted(called)
                },
            }, "ast_parameter_methods"))
