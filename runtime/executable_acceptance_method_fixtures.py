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
    assigned = _self_attributes(nodes, ast.Store)
    for name in sorted(_self_attributes(nodes, ast.Load) - assigned - methods):
        raw.setdefault(name, {"__fixture__": "safe_method_attribute"})
    return raw, {key: materialize(value) for key, value in raw.items()}


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
