"""Interpret declarative structural contract-family recognition rules."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


DEFAULT_PATH = Path(__file__).resolve().parents[1] / "knowledge" / "contract_families" / "structural_recognition.json"
SUPPORTED_OPERATORS = {
    "equals", "falsy", "gte", "intersects", "contains", "contains_all",
    "contains_count_at_least", "ends_with_ci", "set_equals", "starts_with_ci", "subset_of", "truthy",
}


@lru_cache(maxsize=1)
def load_structural_family_rules(path: str | None = None) -> dict[str, Any]:
    payload = json.loads(Path(path or DEFAULT_PATH).read_text(encoding="utf-8"))
    if payload.get("schema_version") != "structural_contract_family_rules.v1":
        raise ValueError("structural contract family rules schema mismatch")
    rules = payload.get("rules")
    if not isinstance(rules, list) or not rules:
        raise ValueError("structural contract family rules must contain rules")
    seen: set[str] = set()
    for rule in rules:
        family_id = str(dict(rule or {}).get("family_id") or "")
        conditions = dict(rule or {}).get("all")
        if not family_id or family_id in seen or not isinstance(conditions, list) or not conditions:
            raise ValueError(f"invalid structural contract family rule: {family_id or '<missing>'}")
        seen.add(family_id)
        for condition in conditions:
            row = dict(condition or {})
            if not row.get("field") or row.get("op") not in SUPPORTED_OPERATORS:
                raise ValueError(f"invalid structural condition in {family_id}")
    return payload


def structural_contract_family(
    evidence: dict[str, Any] | None,
    side_effect_contract: dict[str, Any] | None = None,
    *,
    rules_path: str | None = None,
) -> str:
    return str(structural_contract_family_rule(evidence, side_effect_contract, rules_path=rules_path).get("family_id") or "")


def structural_contract_family_rule(
    evidence: dict[str, Any] | None,
    side_effect_contract: dict[str, Any] | None = None,
    *,
    rules_path: str | None = None,
) -> dict[str, Any]:
    facts = _normalized_facts(evidence, side_effect_contract)
    for rule in load_structural_family_rules(rules_path)["rules"]:
        if all(_matches(facts, dict(condition)) for condition in rule["all"]):
            return dict(rule)
    return {}


def _normalized_facts(
    evidence: dict[str, Any] | None, side_effect_contract: dict[str, Any] | None
) -> dict[str, Any]:
    facts = dict(evidence or {})
    usage = dict(facts.get("argument_usage_types") or {})
    output_type = str(facts.get("inferred_output_type") or "")
    union_members = []
    if output_type.startswith("Union[") and output_type.endswith("]"):
        union_members = [part.strip() for part in output_type[6:-1].split(",")]
    facts.update(
        {
            "decorators": [str(value).lower().rsplit(".", 1)[-1] for value in facts.get("decorators", [])],
            "usage": usage,
            "usage_types": list(usage.values()),
            "output_type": output_type,
            "output_union_members": union_members,
            "observed_effects": list(facts.get("observed_side_effects") or []),
            "declared_effects": list(dict(side_effect_contract or {}).get("declared") or []),
        }
    )
    return facts


def _matches(facts: dict[str, Any], condition: dict[str, Any]) -> bool:
    actual = _field_value(facts, str(condition["field"]))
    operator = str(condition["op"])
    expected = condition.get("value")
    if operator == "equals":
        return actual == expected
    if operator == "truthy":
        return bool(actual)
    if operator == "falsy":
        return not actual
    if operator == "gte":
        return _number(actual) >= _number(expected)
    if operator == "starts_with_ci":
        return str(actual).lower().startswith(str(expected).lower())
    if operator == "ends_with_ci":
        return str(actual).lower().endswith(str(expected).lower())
    actual_set = set(actual or [])
    expected_set = set(expected or [])
    if operator == "contains":
        return expected in actual_set
    if operator == "contains_all":
        return expected_set <= actual_set
    if operator == "intersects":
        return bool(actual_set & expected_set)
    if operator == "set_equals":
        return actual_set == expected_set
    if operator == "subset_of":
        return actual_set <= expected_set
    if operator == "contains_count_at_least":
        return list(actual or []).count(expected) >= int(condition.get("count") or 1)
    return False


def _field_value(facts: dict[str, Any], field: str) -> Any:
    value: Any = facts
    for part in field.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


def _number(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
