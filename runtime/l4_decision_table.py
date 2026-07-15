"""Declarative summary of repeatable L4.0 decisions."""

from __future__ import annotations

from typing import Any


L4_DECISION_RULES: list[dict[str, Any]] = [
    {
        "rule_id": "prompt_ready_template_supported",
        "scope": "prompt_to_product",
        "conditions": {
            "prompt_adequacy_status": "ready",
            "supported_template": "present",
        },
        "next_action": "build_verified_system_package",
        "reason_code": "prompt_ready_and_template_supported",
        "llm_allowed": False,
    },
    {
        "rule_id": "prompt_ready_template_missing",
        "scope": "prompt_to_product",
        "conditions": {
            "prompt_adequacy_status": "ready",
            "supported_template": "missing",
        },
        "next_action": "request_l45_semantic_hypothesis",
        "reason_code": "no_supported_package_template",
        "llm_allowed": True,
    },
    {
        "rule_id": "prompt_needs_clarification",
        "scope": "prompt_to_product",
        "conditions": {
            "prompt_adequacy_status": "needs_clarification",
        },
        "next_action": "ask_clarification",
        "reason_code": "prompt_needs_clarification",
        "llm_allowed": False,
    },
    {
        "rule_id": "prompt_unsupported",
        "scope": "prompt_to_product",
        "conditions": {
            "prompt_adequacy_status": "unsupported",
        },
        "next_action": "stop_unsupported",
        "reason_code": "prompt_unsupported_by_policy",
        "llm_allowed": False,
    },
    {
        "rule_id": "l45_new_template_candidate_accepted",
        "scope": "semantic_validation",
        "conditions": {
            "l4_semantic_validation_status": "accepted",
            "hypothesis_type": "new_template_candidate",
        },
        "next_action": "record_template_backlog",
        "reason_code": "l45_new_template_candidate_accepted_by_l4_gate",
        "llm_allowed": False,
    },
    {
        "rule_id": "l45_proposal_blocked",
        "scope": "semantic_validation",
        "conditions": {
            "l4_semantic_validation_status": "blocked",
        },
        "next_action": "blocked",
        "reason_code": "l45_proposal_failed_l4_validation",
        "llm_allowed": False,
    },
]


def decision_table_catalog() -> dict[str, Any]:
    return {
        "artifact_type": "L4DecisionTable",
        "status": "ok",
        "rule_count": len(L4_DECISION_RULES),
        "rules": [dict(rule) for rule in L4_DECISION_RULES],
        "principle": "repeated semantic decisions should crystallize into deterministic rules, gates, templates or tests",
    }


def match_prompt_product_rule(*, prompt_adequacy_status: str, supported_template: str | None) -> dict[str, Any] | None:
    template_state = "present" if supported_template else "missing"
    for rule in L4_DECISION_RULES:
        conditions = dict(rule.get("conditions", {}))
        if rule.get("scope") != "prompt_to_product":
            continue
        if conditions.get("prompt_adequacy_status") != prompt_adequacy_status:
            continue
        if "supported_template" in conditions and conditions["supported_template"] != template_state:
            continue
        return dict(rule)
    return None
