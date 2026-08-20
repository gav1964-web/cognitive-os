"""Interpret KB-backed first-slice viability rules."""

from __future__ import annotations

import ast
import builtins
import json
import textwrap
from functools import lru_cache
from pathlib import Path
from collections.abc import Mapping
from typing import Any


DEFAULT_PATH = Path(__file__).resolve().parents[1] / "knowledge" / "architecture_patterns" / "first_slice_viability.json"


@lru_cache(maxsize=1)
def load_first_slice_viability(path: str | None = None) -> dict[str, Any]:
    payload = json.loads((Path(path) if path else DEFAULT_PATH).read_text(encoding="utf-8"))
    if payload.get("schema_version") != "first_slice_viability.v1":
        raise ValueError("first-slice viability KB must use schema_version first_slice_viability.v1")
    if not isinstance(payload.get("rules"), list):
        raise ValueError("first-slice viability KB must contain rules")
    seen = set()
    for rule in payload["rules"]:
        rule_id = str(dict(rule or {}).get("rule_id") or "")
        if not rule_id or rule_id in seen or not isinstance(dict(rule or {}).get("score_delta"), int):
            raise ValueError("first-slice viability rules require unique ids and integer deltas")
        seen.add(rule_id)
        _validate_matchers(dict(dict(rule).get("match") or {}))
    return payload


def first_slice_viability(
    source: str,
    context: dict[str, Any] | None = None,
    *,
    knowledge_rule: str = "",
) -> dict[str, Any]:
    payload = load_first_slice_viability()
    facts = _facts(source, context or {}, knowledge_rule, payload)
    score = 0
    matched = []
    for rule in payload["rules"]:
        if not isinstance(rule, dict) or not _matches(dict(rule.get("match") or {}), facts):
            continue
        delta = int(rule.get("score_delta") or 0)
        score += delta
        matched.append({
            "rule_id": str(rule.get("rule_id") or ""),
            "score_delta": delta,
            "reason": str(rule.get("reason") or ""),
        })
    minimum = int(payload.get("minimum_score") or 0)
    matched_ids = {row["rule_id"] for row in matched}
    reselection_required = any(
        bool(rule.get("reselection_required"))
        for rule in payload["rules"]
        if isinstance(rule, dict) and str(rule.get("rule_id") or "") in matched_ids
    )
    return {
        "status": "eligible" if score >= minimum else "deferred",
        "reselection_required": reselection_required,
        "receiver_fixture_status": facts["receiver_fixture_status"],
        "runtime_call_scope": facts["runtime_call_scope"],
        "score": score,
        "minimum_score": minimum,
        "matched_rules": matched,
        "source": "knowledge/architecture_patterns/first_slice_viability.json",
    }


def _facts(
    source: str,
    context: dict[str, Any],
    knowledge_rule: str,
    payload: dict[str, Any],
) -> dict[str, str]:
    normalized = source.replace("\\", "/").lower()
    path, _, symbol = normalized.partition(":")
    symbol = symbol.split("(", 1)[0].rsplit(".", 1)[-1]
    raw_snippet = context.get("snippet")
    raw_readiness = context.get("dependency_readiness")
    snippet = dict(raw_snippet) if isinstance(raw_snippet, Mapping) else {
        "text": str(raw_snippet or ""),
        "target_binding": context.get("target_binding"),
        "structural_contract": context.get("structural_contract"),
    }
    readiness = dict(raw_readiness) if isinstance(raw_readiness, Mapping) else {}
    decorators = list(snippet.get("decorators") or context.get("decorators") or [])
    target_binding = str(snippet.get("target_binding") or context.get("target_binding") or "").lower()
    decorator_text = " ".join(str(item).lower() for item in decorators)
    snippet_text = str(snippet.get("text") or "").lower()
    runtime_call_scope = _runtime_call_scope(snippet_text)
    side_effects = list(context.get("contract_side_effects") or context.get("side_effects") or snippet.get("side_effects") or [])
    receiver_kind = _receiver_kind(target_binding, decorator_text, snippet_text)
    structural = dict(snippet.get("structural_contract") or {})
    return {
        "source": normalized,
        "path": f"/{path}",
        "symbol": symbol,
        "knowledge_rule": knowledge_rule.lower(),
        "target_binding": target_binding,
        "receiver_kind": receiver_kind,
        "receiver_fixture_status": _receiver_fixture_status(
            receiver_kind, target_binding, snippet_text, structural, runtime_call_scope
        ),
        "runtime_call_scope": runtime_call_scope,
        "dependency_status": str(readiness.get("status") or "").lower(),
        "decorators": decorator_text,
        "owner_class": str(snippet.get("owner_class") or context.get("owner_class") or "").lower(),
        "snippet_text": snippet_text,
        "side_effects": " ".join(str(item).lower() for item in side_effects),
        "direct_side_effects": " ".join(
            str(item).lower() for item in list(structural.get("observed_side_effects") or [])
        ),
        "state_mutation": str(bool(structural.get("state_mutation"))).lower(),
        "calls": " ".join(str(item).lower() for item in list(context.get("unresolved_calls") or [])),
        "input_complexity": _input_complexity_fact(snippet, payload),
    }


def _receiver_kind(target_binding: str, decorators: str, snippet_text: str) -> str:
    if target_binding not in {"method_symbol", "ambiguous_method_symbol"}:
        return "none"
    if "staticmethod" in decorators or "classmethod" in decorators:
        return "independent"
    if "self." in snippet_text or "super(" in snippet_text:
        return "instance"
    return "stateless_instance"


def _receiver_fixture_status(
    receiver_kind: str,
    target_binding: str,
    snippet_text: str,
    structural: dict[str, Any],
    runtime_call_scope: str,
) -> str:
    if receiver_kind != "instance":
        return "not_required"
    if target_binding == "ambiguous_method_symbol":
        return "ambiguous_owner"
    if "super(" in snippet_text:
        return "unsupported_inheritance"
    if structural.get("source_body_complete") is not True:
        return "source_incomplete"
    if structural.get("state_mutation") is True:
        return "state_mutation"
    if runtime_call_scope == "external_global":
        return "runtime_dependency"
    return "source_isolated_ready"


def _runtime_call_scope(snippet_text: str) -> str:
    try:
        tree = ast.parse(textwrap.dedent(snippet_text))
    except (SyntaxError, ValueError):
        return "unknown"
    builtin_names = set(dir(builtins))
    function = next(
        (node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))),
        None,
    )
    parameters = {
        arg.arg
        for arg in [
            *list(function.args.posonlyargs if function else []),
            *list(function.args.args if function else []),
            *list(function.args.kwonlyargs if function else []),
        ]
    }
    local_names = {
        node.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store)
    }
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        root = node.func
        while isinstance(root, ast.Attribute):
            root = root.value
        if isinstance(root, ast.Name) and root.id not in (
            {"self", "cls"} | builtin_names | parameters | local_names
        ):
            return "external_global"
    return "receiver_or_builtin"


def _input_complexity_fact(snippet: dict[str, Any], payload: dict[str, Any]) -> str:
    structural = dict(snippet.get("structural_contract") or {})
    usage = {str(name): str(value) for name, value in dict(structural.get("argument_usage_types") or {}).items()}
    protocol_names = {name for name, value in usage.items() if value == "ProtocolLike"}
    if protocol_names:
        signature = dict(snippet.get("signature") or {})
        annotations = {
            str(row.get("name")): str(row.get("annotation") or "").strip()
            for row in signature.get("args") or []
            if isinstance(row, dict) and row.get("name")
        }
        if all(annotations.get(name) for name in protocol_names):
            return "declared_protocol"
        return "object_protocol"
    return _input_complexity(
        str(snippet.get("text") or ""),
        {str(item) for item in payload.get("materializable_parameter_attributes") or []},
    )


def _input_complexity(snippet: str, materializable_attributes: set[str]) -> str:
    if not snippet or "..." in snippet:
        return "unknown"
    try:
        tree = ast.parse(snippet)
    except (SyntaxError, ValueError):
        return "unknown"
    function = next(
        (node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))),
        None,
    )
    if function is None:
        return "unknown"
    parameters = {
        arg.arg
        for arg in [*function.args.posonlyargs, *function.args.args, *function.args.kwonlyargs]
        if arg.arg not in {"self", "cls"}
    }
    for node in ast.walk(function):
        if not isinstance(node, ast.Attribute) or node.attr in materializable_attributes:
            continue
        root = node.value
        while isinstance(root, (ast.Attribute, ast.Subscript)):
            root = root.value
        if isinstance(root, ast.Name) and root.id in parameters:
            return "object_protocol"
    return "scalar_or_structural"


def _matches(match: dict[str, Any], facts: dict[str, str]) -> bool:
    checks = []
    for key, values in match.items():
        candidates = [str(value).lower() for value in list(values or [])]
        if key.endswith("_contains_any"):
            fact_name, operation = key[: -len("_contains_any")], "contains_any"
        elif key.endswith("_in"):
            fact_name, operation = key[:-3], "in"
        else:
            raise ValueError(f"unsupported first-slice viability matcher: {key}")
        fact = facts.get(fact_name, "")
        if operation == "in":
            checks.append(fact in candidates)
        elif operation == "contains_any":
            checks.append(any(candidate in fact for candidate in candidates))
    return bool(checks) and all(checks)


def _validate_matchers(match: dict[str, Any]) -> None:
    allowed_facts = {
        "source", "path", "symbol", "knowledge_rule", "target_binding", "dependency_status",
        "decorators", "owner_class", "snippet_text", "side_effects", "calls", "receiver_kind",
        "input_complexity", "receiver_fixture_status", "runtime_call_scope", "direct_side_effects", "state_mutation",
    }
    for key, values in match.items():
        suffix = "_contains_any" if key.endswith("_contains_any") else "_in" if key.endswith("_in") else ""
        if not suffix or key[: -len(suffix)] not in allowed_facts or not isinstance(values, list) or not values:
            raise ValueError(f"invalid first-slice viability matcher: {key}")
