from __future__ import annotations

from pathlib import Path

import pytest

from runtime.semantic_resolution_rules import SemanticResolutionRulesError, load_semantic_resolution_rules


ROOT = Path(__file__).resolve().parents[2]


def test_semantic_resolution_rules_load_existing_and_developer_rules():
    rules = load_semantic_resolution_rules(str(ROOT / "config" / "semantic_resolution_rules.json"))

    existing = {row["rule_id"]: row for row in rules["existing_resolution_rules"]}
    developer = {row["rule_id"]: row for row in rules["developer_request_rules"]}
    assert "csv_sort_cli" in existing
    assert existing["generic_file_converter_cli"]["include_conversion_recipe"] is True
    assert "behavior_question" in developer
    assert rules["default_developer_request"]["request_id"] == "add_stage2_template_or_generic_cli_builder"


def test_semantic_resolution_rules_reject_missing_required_template(tmp_path: Path):
    path = tmp_path / "rules.json"
    path.write_text(
        """{
  "schema_version": "semantic_resolution_rules.v1",
  "status": "active",
  "existing_resolution_rules": [{"predicate": "csv_sort_prompt"}],
  "developer_request_rules": [],
  "default_developer_request": {"request_id": "x", "missing_capability": "y"}
}
""",
        encoding="utf-8",
    )

    with pytest.raises(SemanticResolutionRulesError, match="required_template"):
        load_semantic_resolution_rules(str(path))
