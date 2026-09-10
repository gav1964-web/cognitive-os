"""Infer bounded instance fixtures for source-isolated methods."""

from __future__ import annotations

import ast
from typing import Any

from .executable_acceptance_materializers import materialize
from .executable_acceptance_policy import method_fixture_policy, sample_value


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
    policy = method_fixture_policy()
    fixture = str(policy.get("delegated_transport_fixture") or "")
    for name in _delegated_transport_calls(symbol, nodes, policy):
        raw.setdefault(name, {"__fixture__": fixture})
    for name in sorted(_self_attributes(nodes, ast.Load) - methods):
        raw.setdefault(name, _inferred_attribute_fixture(name, nodes))
    return raw, {key: materialize(value) for key, value in raw.items()}


def _delegated_transport_calls(symbol: str, nodes: list[ast.AST], policy: dict[str, Any]) -> set[str]:
    allowed = set(policy.get("delegated_transport_methods") or [])
    target = next((node for node in nodes if getattr(node, "name", None) == symbol), None)
    if target is None or not policy.get("delegated_transport_fixture"):
        return set()
    return {
        item.func.attr
        for item in ast.walk(target)
        if isinstance(item, ast.Call)
        and isinstance(item.func, ast.Attribute)
        and isinstance(item.func.value, ast.Name)
        and item.func.value.id == "self"
        and item.func.attr in allowed
    }


def _inferred_attribute_fixture(name: str, nodes: list[ast.AST]) -> Any:
    policy = method_fixture_policy()
    callable_fixture = str(dict(policy.get("callable_attribute_fixtures") or {}).get(name) or "")
    if callable_fixture and _called_self_attribute(name, nodes):
        return {"__fixture__": callable_fixture}
    if policy.get("nullable_comparison_enabled") and _compared_to_none(name, nodes):
        return None
    if _used_as_boolean_condition(name, nodes):
        return _successful_boolean_branch_value(
            name, nodes, bool(policy.get("boolean_condition_value", False))
        )
    if _used_as_mapping_value(name, nodes):
        return policy.get("mapping_value_sample", "sample")
    mapping_argument = _required_mapping_argument(name, nodes)
    if mapping_argument:
        key = sample_value("", mapping_argument)
        if key is None or isinstance(key, (dict, list, tuple)):
            key = str(policy.get("required_mapping_key_sample") or "sample")
        fixture = str(policy.get("required_mapping_value_fixture") or "safe_method_attribute")
        return {key: {"__fixture__": fixture}}
    if _used_as_numeric_value(name, nodes, set(policy.get("numeric_receiver_calls") or [])):
        return int(policy.get("numeric_receiver_attribute_sample") or 1)
    if _used_in_ordering_comparison(name, nodes):
        return int(policy.get("comparison_receiver_attribute_sample") or 16)
    if _used_as_numpy_array_input(name, nodes):
        return {"__fixture__": "numpy_array", "items": list(range(16))}
    if _used_as_text_value(name, nodes):
        return "sample"
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


def _called_self_attribute(name: str, nodes: list[ast.AST]) -> bool:
    return any(
        isinstance(item, ast.Call)
        and isinstance(item.func, ast.Attribute)
        and isinstance(item.func.value, ast.Name)
        and item.func.value.id == "self"
        and item.func.attr == name
        for node in nodes for item in ast.walk(node)
    )


def _used_as_boolean_condition(name: str, nodes: list[ast.AST]) -> bool:
    for node in nodes:
        for item in ast.walk(node):
            if (
                isinstance(item, (ast.If, ast.IfExp, ast.While))
                and _direct_boolean_attribute(item.test) == name
            ):
                return True
    return False


def _successful_boolean_branch_value(name: str, nodes: list[ast.AST], default: bool) -> bool:
    for node in nodes:
        for item in ast.walk(node):
            if not isinstance(item, ast.If) or _direct_boolean_attribute(item.test) != name:
                continue
            body_raises = any(isinstance(part, ast.Raise) for statement in item.body for part in ast.walk(statement))
            else_raises = any(isinstance(part, ast.Raise) for statement in item.orelse for part in ast.walk(statement))
            if else_raises and not body_raises:
                return True
            if body_raises and not else_raises:
                return False
    return default


def _direct_boolean_attribute(node: ast.AST) -> str:
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        node = node.operand
    if (
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "self"
    ):
        return node.attr
    return ""


def _used_in_ordering_comparison(name: str, nodes: list[ast.AST]) -> bool:
    return any(
        isinstance(item, ast.Compare)
        and name in _loaded_self_attributes(item)
        and any(isinstance(operator, (ast.Gt, ast.GtE, ast.Lt, ast.LtE)) for operator in item.ops)
        for node in nodes for item in ast.walk(node)
    )


def _used_as_numpy_array_input(name: str, nodes: list[ast.AST]) -> bool:
    return any(
        isinstance(item, ast.Call)
        and isinstance(item.func, ast.Attribute)
        and item.func.attr in {"array", "asarray"}
        and bool(item.args)
        and name in _loaded_self_attributes(item.args[0])
        for node in nodes for item in ast.walk(node)
    )


def _compared_to_none(name: str, nodes: list[ast.AST]) -> bool:
    for node in nodes:
        for item in ast.walk(node):
            if not isinstance(item, ast.Compare) or name not in _loaded_self_attributes(item):
                continue
            if any(isinstance(value, ast.Constant) and value.value is None for value in [item.left, *item.comparators]):
                return True
    return False


def _used_as_mapping_value(name: str, nodes: list[ast.AST]) -> bool:
    return any(
        name in _loaded_self_attributes(value)
        for node in nodes for item in ast.walk(node) if isinstance(item, ast.Dict)
        for value in item.values
    )


def _required_mapping_argument(name: str, nodes: list[ast.AST]) -> str:
    for node in nodes:
        for item in ast.walk(node):
            if (
                isinstance(item, ast.Call)
                and isinstance(item.func, ast.Attribute)
                and item.func.attr == "pop"
                and len(item.args) == 1
                and not item.keywords
                and isinstance(item.args[0], ast.Name)
                and isinstance(item.func.value, ast.Attribute)
                and isinstance(item.func.value.value, ast.Name)
                and item.func.value.value.id == "self"
                and item.func.value.attr == name
            ):
                return item.args[0].id
    return ""


def _used_as_numeric_value(name: str, nodes: list[ast.AST], call_names: set[str]) -> bool:
    for node in nodes:
        for item in ast.walk(node):
            if isinstance(item, ast.BinOp) and name in _loaded_self_attributes(item):
                return True
            if not isinstance(item, ast.Call):
                continue
            call_name = getattr(item.func, "id", "") or getattr(item.func, "attr", "")
            values = [*item.args, *[keyword.value for keyword in item.keywords]]
            if call_name in call_names and any(name in _loaded_self_attributes(value) for value in values):
                return True
    return False


def _used_as_text_value(name: str, nodes: list[ast.AST]) -> bool:
    for node in nodes:
        for item in ast.walk(node):
            if isinstance(item, ast.FormattedValue) and name in _loaded_self_attributes(item.value):
                return True
            if (
                isinstance(item, ast.Call)
                and isinstance(item.func, ast.Attribute)
                and item.func.attr in {"format", "format_map"}
                and any(name in _loaded_self_attributes(value) for value in [*item.args, *[part.value for part in item.keywords]])
            ):
                return True
    return False


def _loaded_self_attributes(node: ast.AST) -> set[str]:
    return {
        item.attr
        for item in ast.walk(node)
        if isinstance(item, ast.Attribute)
        and isinstance(item.value, ast.Name)
        and item.value.id == "self"
        and isinstance(item.ctx, ast.Load)
    }


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
