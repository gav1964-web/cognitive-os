"""Declarative summary of repeatable L4.0 decisions."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RULES_PATH = ROOT / "config" / "l4_decision_rules.json"


class L4DecisionRulesError(RuntimeError):
    """Raised when L4 decision rules are invalid."""


@lru_cache(maxsize=1)
def load_l4_decision_rules(path: str | None = None) -> dict[str, Any]:
    source = Path(path) if path else RULES_PATH
    payload = json.loads(source.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "l4_decision_rules.v1":
        raise L4DecisionRulesError("L4 decision rules must use schema_version l4_decision_rules.v1")
    if payload.get("status") != "active":
        raise L4DecisionRulesError("L4 decision rules must be active")
    rules = payload.get("rules")
    if not isinstance(rules, list) or not rules:
        raise L4DecisionRulesError("L4 decision rules require non-empty rules list")
    for row in rules:
        if not isinstance(row, dict):
            raise L4DecisionRulesError("L4 decision rule must be object")
        for field in ("rule_id", "scope", "conditions", "next_action", "reason_code"):
            if field not in row:
                raise L4DecisionRulesError(f"L4 decision rule requires {field}")
    return payload


def decision_table_catalog() -> dict[str, Any]:
    payload = load_l4_decision_rules()
    rules = sorted([dict(rule) for rule in payload["rules"]], key=lambda row: int(row.get("priority") or 100))
    return {
        "artifact_type": "L4DecisionTable",
        "status": "ok",
        "rule_count": len(rules),
        "rules": rules,
        "principle": payload.get("principle"),
    }


def match_prompt_product_rule(*, prompt_adequacy_status: str, supported_template: str | None) -> dict[str, Any] | None:
    return match_prompt_product_transition_rule(
        prompt_adequacy_status=prompt_adequacy_status,
        supported_template=supported_template,
        terminal_unsupported_boundary=False,
    )


def match_prompt_product_transition_rule(
    *,
    prompt_adequacy_status: str,
    supported_template: str | None,
    terminal_unsupported_boundary: bool,
) -> dict[str, Any] | None:
    payload = load_l4_decision_rules()
    template_state = "present" if supported_template else "missing"
    for rule in sorted(payload["rules"], key=lambda row: int(row.get("priority") or 100)):
        conditions = dict(rule.get("conditions", {}))
        if rule.get("scope") != "prompt_to_product":
            continue
        if "terminal_unsupported_boundary" in conditions and conditions["terminal_unsupported_boundary"] != terminal_unsupported_boundary:
            continue
        if "prompt_adequacy_status" in conditions and conditions.get("prompt_adequacy_status") != prompt_adequacy_status:
            continue
        if "supported_template" in conditions and conditions["supported_template"] != template_state:
            continue
        return dict(rule)
    return None


def prompt_product_escalation_reason(name: str) -> str:
    return str(dict(load_l4_decision_rules().get("prompt_escalation_reasons") or {}).get(name) or name)


def terminal_unsupported_markers() -> set[str]:
    return {str(item) for item in load_l4_decision_rules().get("terminal_unsupported_markers", [])}


def terminal_secret_risk_markers() -> set[str]:
    return {str(item) for item in load_l4_decision_rules().get("terminal_secret_risk_markers", [])}
