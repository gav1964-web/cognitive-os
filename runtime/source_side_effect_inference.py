"""Infer source side effects using declarative AST call rules."""

from __future__ import annotations

import ast
import json
from functools import lru_cache
from pathlib import Path
from typing import Any


DEFAULT_POLICY = Path(__file__).resolve().parents[1] / "config" / "source_side_effect_inference.json"


@lru_cache(maxsize=1)
def load_source_side_effect_policy() -> dict[str, Any]:
    payload = json.loads(DEFAULT_POLICY.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "source_side_effect_inference.v1":
        raise ValueError("source side-effect policy must use schema_version source_side_effect_inference.v1")
    return payload


def infer_ast_side_effects(node: ast.AST, text: str) -> list[str]:
    policy = load_source_side_effect_policy()
    calls = {_call_name(child.func).lower() for child in ast.walk(node) if isinstance(child, ast.Call)}
    effects = {
        str(rule["id"])
        for rule in policy.get("effects", [])
        if isinstance(rule, dict) and _rule_matches(rule, calls)
    }
    memory = dict(policy.get("memory_state") or {})
    node_names = set(str(item) for item in memory.get("ast_nodes", []))
    if any(type(child).__name__ in node_names for child in ast.walk(node)):
        effects.add("memory_state")
    lowered = text.lower()
    if any(str(marker).lower() in lowered for marker in memory.get("text_contains", [])):
        effects.add("memory_state")
    return sorted(effects)


def _rule_matches(rule: dict[str, Any], calls: set[str]) -> bool:
    exact = {str(item).lower() for item in rule.get("call_exact", [])}
    contains = [str(item).lower() for item in rule.get("call_contains", [])]
    return any(call in exact or any(token in call for token in contains) for call in calls)


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _call_name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    return ""
