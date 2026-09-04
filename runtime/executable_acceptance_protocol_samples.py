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
    result_attributes = _method_result_attributes(node, parameters)
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
                    method: _method_fixture(name, method, result_attributes)
                    for method in sorted(called)
                },
            }, "ast_parameter_methods"))


def add_mapping_protocol_samples(
    node: ast.AST,
    parameters: set[str],
    candidates: dict[str, list[tuple[int, Any, str]]],
    *,
    priority: int,
    methods: set[str],
    sample: dict[str, Any],
) -> None:
    for item in ast.walk(node):
        if not isinstance(item, ast.Call) or not isinstance(item.func, ast.Attribute):
            continue
        owner = item.func.value
        if item.func.attr == "get" and (len(item.args) > 2 or item.keywords):
            continue
        if isinstance(owner, ast.Name) and owner.id in parameters and item.func.attr in methods:
            candidates[owner.id].append(
                (priority, dict(sample), f"ast_mapping_protocol:{item.func.attr}")
            )


def _method_result_attributes(
    node: ast.AST, parameters: set[str]
) -> dict[tuple[str, str], set[str]]:
    bindings: dict[str, tuple[str, str]] = {}
    for item in ast.walk(node):
        if not isinstance(item, (ast.Assign, ast.AnnAssign)):
            continue
        targets = item.targets if isinstance(item, ast.Assign) else [item.target]
        value = item.value
        if not isinstance(value, ast.Call) or not isinstance(value.func, ast.Attribute):
            continue
        if not isinstance(value.func.value, ast.Name) or value.func.value.id not in parameters:
            continue
        for target in targets:
            if isinstance(target, ast.Name):
                bindings[target.id] = (value.func.value.id, value.func.attr)
    attributes: dict[tuple[str, str], set[str]] = {}
    for item in ast.walk(node):
        if isinstance(item, ast.Attribute) and isinstance(item.value, ast.Name):
            binding = bindings.get(item.value.id)
            if binding:
                attributes.setdefault(binding, set()).add(item.attr)
    return attributes


def _method_fixture(
    parameter: str, method: str, attributes: dict[tuple[str, str], set[str]]
) -> dict[str, Any]:
    fields = attributes.get((parameter, method), set())
    if not fields:
        return {"__fixture__": "callable_empty_list"}
    return {
        "__fixture__": "callable_declared_model",
        "fields": {name: "sample" for name in sorted(fields)},
    }
