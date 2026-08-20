"""Safe protocol fixtures inferred from calls on function parameters."""

from __future__ import annotations

import ast
from typing import Any


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
