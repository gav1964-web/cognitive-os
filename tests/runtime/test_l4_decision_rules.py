from __future__ import annotations

from pathlib import Path

import pytest

from runtime.l4_decision_table import (
    L4DecisionRulesError,
    load_l4_decision_rules,
    match_prompt_product_transition_rule,
    terminal_secret_risk_markers,
    terminal_unsupported_markers,
)


ROOT = Path(__file__).resolve().parents[2]


def test_l4_decision_rules_load_prompt_to_product_transitions():
    rules = load_l4_decision_rules(str(ROOT / "config" / "l4_decision_rules.json"))

    assert "mobile_app" in terminal_unsupported_markers()
    assert "secrets" in terminal_secret_risk_markers()
    assert rules["prompt_escalation_reasons"]["ready_missing_template"] == "no_supported_package_template"
    rule = match_prompt_product_transition_rule(
        prompt_adequacy_status="ready",
        supported_template="csv_sort_cli",
        terminal_unsupported_boundary=False,
    )
    assert rule is not None
    assert rule["next_action"] == "build_verified_system_package"


def test_l4_decision_rules_cover_all_configured_rule_ids():
    rules = load_l4_decision_rules(str(ROOT / "config" / "l4_decision_rules.json"))
    rule_ids = {str(rule["rule_id"]) for rule in rules["rules"]}

    assert {
        "prompt_ready_template_supported",
        "prompt_terminal_unsupported_boundary",
        "prompt_needs_clarification",
        "prompt_too_broad",
        "prompt_unsupported",
        "prompt_ready_template_missing",
        "l45_new_template_candidate_accepted",
        "l45_proposal_blocked",
    } <= rule_ids


def test_l4_decision_rules_match_terminal_unsupported_before_generic_status():
    rule = match_prompt_product_transition_rule(
        prompt_adequacy_status="unsupported",
        supported_template=None,
        terminal_unsupported_boundary=True,
    )

    assert rule is not None
    assert rule["rule_id"] == "prompt_terminal_unsupported_boundary"
    assert rule["next_action"] == "ask_clarification"


def test_l4_decision_rules_reject_missing_next_action(tmp_path: Path):
    path = tmp_path / "rules.json"
    path.write_text(
        """{
  "schema_version": "l4_decision_rules.v1",
  "status": "active",
  "rules": [{"rule_id": "bad", "scope": "prompt_to_product", "conditions": {}}]
}
""",
        encoding="utf-8",
    )

    with pytest.raises(L4DecisionRulesError, match="next_action"):
        load_l4_decision_rules(str(path))
