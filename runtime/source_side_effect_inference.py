"""Infer source side effects using declarative AST call rules."""

from __future__ import annotations

import ast
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from runtime.source_ast_scope import callable_scope_walk
from runtime.source_contract_helpers import target_mutates_external_state


DEFAULT_POLICY = Path(__file__).resolve().parents[1] / "config" / "source_side_effect_inference.json"


@lru_cache(maxsize=1)
def load_source_side_effect_policy() -> dict[str, Any]:
    payload = json.loads(DEFAULT_POLICY.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "source_side_effect_inference.v1":
        raise ValueError("source side-effect policy must use schema_version source_side_effect_inference.v1")
    return payload


def infer_ast_side_effects(node: ast.AST, text: str) -> list[str]:
    policy = load_source_side_effect_policy()
    call_nodes = [child for child in callable_scope_walk(node) if isinstance(child, ast.Call)]
    calls = {_call_name(child.func).lower() for child in call_nodes}
    effects = {
        str(rule["id"])
        for rule in policy.get("effects", [])
        if isinstance(rule, dict) and _rule_matches(rule, calls)
    }
    memory = dict(policy.get("memory_state") or {})
    node_names = set(str(item) for item in memory.get("ast_nodes", []))
    if any(type(child).__name__ in node_names for child in callable_scope_walk(node)):
        effects.add("memory_state")
    if _mutates_external_state(node):
        effects.add("memory_state")
    lowered = text.lower()
    if any(str(marker).lower() in lowered for marker in memory.get("text_contains", [])):
        effects.add("memory_state")
    effects.update(_open_effects(call_nodes))
    return sorted(effects)


def selection_side_effects(effects: list[str]) -> list[str]:
    contract_only = {str(item) for item in load_source_side_effect_policy().get("contract_only_effects", [])}
    return sorted(set(effects) - contract_only)


def _open_effects(calls: list[ast.Call]) -> set[str]:
    effects = set()
    for call in calls:
        name = _call_name(call.func).lower()
        if name != "open" and not name.endswith(".open"):
            continue
        mode = _open_mode(call)
        effects.add("filesystem_write" if any(token in mode for token in "wax+") else "filesystem_read")
    return effects


def _open_mode(call: ast.Call) -> str:
    values = [call.args[1]] if len(call.args) > 1 else []
    values.extend(keyword.value for keyword in call.keywords if keyword.arg == "mode")
    return next((str(value.value).lower() for value in values if isinstance(value, ast.Constant)), "r")


def _rule_matches(rule: dict[str, Any], calls: set[str]) -> bool:
    exact = {str(item).lower() for item in rule.get("call_exact", [])}
    contains = [str(item).lower() for item in rule.get("call_contains", [])]
    excluded = tuple(str(item).lower() for item in rule.get("exclude_prefix", []))
    candidates = {call for call in calls if not call.startswith(excluded)}
    return any(call in exact or any(token in call for token in contains) for call in candidates)


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Call):
        return _call_name(node.func)
    if isinstance(node, ast.Attribute):
        base = _call_name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    return ""


def _mutates_external_state(node: ast.AST) -> bool:
    local_names = {
        target.id
        for child in callable_scope_walk(node)
        if isinstance(child, (ast.Assign, ast.AnnAssign))
        for target in (child.targets if isinstance(child, ast.Assign) else [child.target])
        if isinstance(target, ast.Name)
    }
    for child in callable_scope_walk(node):
        if not isinstance(child, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            continue
        targets = child.targets if isinstance(child, ast.Assign) else [child.target]
        if any(target_mutates_external_state(target, local_names) for target in targets):
            return True
    return False
