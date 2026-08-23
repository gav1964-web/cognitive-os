"""Infer nested read-only object fixtures from parameter attribute access."""

from __future__ import annotations

import ast
from typing import Any
from .executable_acceptance_inherited_samples import add_inherited_method_samples

Candidates = dict[str, list[tuple[int, Any, str]]]
FunctionNode = ast.FunctionDef | ast.AsyncFunctionDef


def add_parameter_attribute_samples(
    tree: ast.Module,
    node: FunctionNode,
    parameters: set[str],
    candidates: Candidates,
    *,
    priority: int,
    attribute_policy: dict[str, Any],
) -> None:
    add_inherited_method_samples(
        tree, node, parameters, candidates, priority=priority + 5,
        profiles=list(attribute_policy.get("inherited_method_fixtures") or []),
    )
    called_paths = {
        path
        for item in ast.walk(node)
        if isinstance(item, ast.Call)
        for path in [_attribute_path(item.func, parameters)]
        if path
    }
    callable_fixtures = dict(attribute_policy.get("callable_protocol_fixtures") or {})
    for path in sorted(called_paths):
        fixture = str(callable_fixtures.get(path[-1]) or "")
        if fixture:
            candidates[path[0]].append((
                priority,
                {"__fixture__": fixture},
                f"ast_parameter_callable_protocol:{path[-1]}",
            ))
    trees: dict[str, dict[str, Any]] = {name: {} for name in parameters}
    for item in ast.walk(node):
        if not isinstance(item, ast.Attribute):
            continue
        path = _attribute_path(item, parameters)
        if not path or path in called_paths:
            continue
        _insert_path(trees[path[0]], path[1:])
    for name, tree in trees.items():
        if tree:
            candidates[name].append((priority, _model(tree, attribute_policy), "ast_parameter_attributes"))


def _attribute_path(node: ast.AST, parameters: set[str]) -> tuple[str, ...]:
    parts: list[str] = []
    current = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if not isinstance(current, ast.Name) or current.id not in parameters:
        return ()
    return (current.id, *reversed(parts))


def _insert_path(tree: dict[str, Any], path: tuple[str, ...]) -> None:
    current = tree
    for field in path:
        value = current.get(field)
        if not isinstance(value, dict):
            value = {}
            current[field] = value
        current = value


def _model(tree: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    fields = {
        name: _model(children, policy) if children else _leaf(name, policy)
        for name, children in sorted(tree.items())
    }
    return {"__fixture__": "declared_model", "type": "AcceptanceInput", "fields": fields}


def _leaf(name: str, policy: dict[str, Any]) -> Any:
    prefixes = tuple(str(item) for item in policy.get("boolean_prefixes") or [])
    if name.startswith(prefixes) or name in set(policy.get("boolean_names") or []):
        return policy.get("boolean_value")
    if name in set(policy.get("integer_names") or []):
        return policy.get("integer_value")
    return policy.get("default")
