"""Classify verifier counterexamples and select config-backed repair playbooks."""

from __future__ import annotations

import ast
import re
from typing import Any

from .programmer_executor_playbooks import load_programmer_executor_playbooks


def classify_verifier_failures(test_result: dict[str, Any]) -> list[dict[str, str]]:
    summary = dict(dict(test_result.get("executable_acceptance_result") or {}).get("summary") or {})
    matches: list[dict[str, str]] = []
    for item in list(summary.get("skipped_targets") or []):
        row = dict(item) if isinstance(item, dict) else {}
        detail = str(row.get("detail") or "")
        failure_class = _detail_failure_class(detail)
        if failure_class:
            matches.append(
                {
                    "class": failure_class,
                    "target": str(row.get("target") or ""),
                    "detail": detail[:1000],
                }
            )
    return matches


def select_repair_playbooks(test_result: dict[str, Any]) -> list[dict[str, Any]]:
    classes = {item["class"] for item in classify_verifier_failures(test_result)}
    selected: list[dict[str, Any]] = []
    for item in load_programmer_executor_playbooks().get("playbooks", []):
        row = dict(item)
        expected = str(dict(row.get("match") or {}).get("verifier_failure_class") or "")
        if expected and expected in classes:
            selected.append(
                {
                    "id": str(row.get("id") or ""),
                    "action": str(row.get("action") or ""),
                    "safe_next_step": str(row.get("safe_next_step") or ""),
                    "repair_guidance": str(row.get("repair_guidance") or ""),
                    "required_gates": [str(gate) for gate in list(row.get("required_gates") or [])],
                    "confidence": float(row.get("confidence") or 0.0),
                    "authority": "advisory_playbook_only",
                }
            )
    return selected


def repair_recipe_errors(recipe: dict[str, Any], playbooks: list[dict[str, Any]]) -> list[str]:
    ids = {str(item.get("id") or "") for item in playbooks}
    boundary_ids = {
        "executor_playbook_duplicate_delimiter_repair",
        "executor_playbook_boundary_noise_repair",
    }
    if not (ids & boundary_ids):
        return []
    methods: set[str] = set()
    has_bidirectional_chain = False
    replacements = [str(recipe.get("replacement_source") or "")]
    replacements.extend(str(dict(item).get("replacement_source") or "") for item in recipe.get("edits") or [])
    for replacement in replacements:
        try:
            tree = ast.parse(replacement)
        except SyntaxError:
            continue
        methods.update(
            node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        )
        has_bidirectional_chain = has_bidirectional_chain or any(
            {"lstrip", "rstrip"}.issubset(_call_chain(node))
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
        )
    if ({"lstrip", "rstrip"} & methods) and "strip" not in methods and not has_bidirectional_chain:
        return ["one_sided_boundary_normalization"]
    return []


def _call_chain(node: ast.Call) -> set[str]:
    methods: set[str] = set()
    current: ast.AST = node
    while isinstance(current, ast.Call) and isinstance(current.func, ast.Attribute):
        methods.add(current.func.attr)
        current = current.func.value
    return methods


def _detail_failure_class(detail: str) -> str:
    match = re.search(r"expected=(.*?);\s*got=(.*)$", detail, flags=re.DOTALL)
    if not match:
        return ""
    expected = _return_value(_literal(match.group(1)))
    observed = _return_value(_literal(match.group(2)))
    if isinstance(expected, str) and isinstance(observed, str):
        collapsed = re.sub(r"([^\w\s])\1+", r"\1", observed)
        if collapsed == expected and collapsed != observed:
            return "duplicate_delimiter"
        if expected and expected in observed:
            prefix, _, suffix = observed.partition(expected)
            boundary = prefix + suffix
            if boundary and all(not char.isalnum() for char in boundary):
                return "boundary_noise"
        if _alphanumeric_skeleton(expected) == _alphanumeric_skeleton(observed):
            expected_internal = expected[1:-1] if len(expected) > 2 else ""
            if any(not char.isalnum() for char in expected_internal):
                return "separator_structure_mismatch"
    if _numeric_component_was_lost(expected, observed):
        return "numeric_component_loss"
    return ""


def _literal(value: str) -> Any:
    try:
        return ast.literal_eval(value.strip())
    except (SyntaxError, ValueError):
        return None


def _return_value(value: Any) -> Any:
    if isinstance(value, dict) and set(value) == {"return_value"}:
        return value["return_value"]
    return value


def _numeric_component_was_lost(expected: Any, observed: Any) -> bool:
    if not isinstance(expected, (list, tuple)) or not isinstance(observed, (list, tuple)):
        return False
    if len(expected) != len(observed):
        return False
    return any(
        isinstance(wanted, int)
        and not isinstance(wanted, bool)
        and wanted != 0
        and isinstance(actual, int)
        and not isinstance(actual, bool)
        and actual == 0
        for wanted, actual in zip(expected, observed)
    )


def _alphanumeric_skeleton(value: str) -> str:
    return "".join(char.casefold() for char in value if char.isalnum())
