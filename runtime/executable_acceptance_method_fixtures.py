"""Infer bounded instance fixtures for source-isolated methods."""

from __future__ import annotations

import ast
from typing import Any

from .executable_acceptance_materializers import materialize
from .executable_acceptance_policy import method_fixture_policy


def method_fixture_values(
    class_name: str,
    symbol: str,
    nodes: list[ast.AST],
    methods: set[str],
) -> tuple[dict[str, Any], dict[str, Any]]:
    raw = dict(
        dict(method_fixture_policy().get("instance_attribute_profiles") or {}).get(
            f"{class_name}.{symbol}"
        )
        or {}
    )
    for name in sorted(_self_attributes(nodes, ast.Load) - methods):
        raw.setdefault(name, _inferred_attribute_fixture(name, nodes))
    return raw, {key: materialize(value) for key, value in raw.items()}


def _inferred_attribute_fixture(name: str, nodes: list[ast.AST]) -> Any:
    operations = {
        item.func.attr
        for node in nodes
        for item in ast.walk(node)
        if isinstance(item, ast.Call)
        and isinstance(item.func, ast.Attribute)
        and isinstance(item.func.value, ast.Attribute)
        and isinstance(item.func.value.value, ast.Name)
        and item.func.value.value.id == "self"
        and item.func.value.attr == name
    }
    if operations & {"get", "items", "keys", "values"}:
        return {}
    if operations & {"append", "extend"}:
        return []
    return {"__fixture__": "safe_method_attribute"}


def _self_attributes(nodes: list[ast.AST], context: type[ast.expr_context]) -> set[str]:
    return {
        item.attr
        for node in nodes
        for item in ast.walk(node)
        if isinstance(item, ast.Attribute)
        and isinstance(item.value, ast.Name)
        and item.value.id == "self"
        and isinstance(item.ctx, context)
    }
