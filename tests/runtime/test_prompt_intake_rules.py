from __future__ import annotations

from pathlib import Path

import pytest

from runtime.prompt_intake_rules import PromptIntakeRulesError, load_prompt_intake_rules, marker_groups, markers


ROOT = Path(__file__).resolve().parents[2]


def test_prompt_intake_rules_load_external_markers():
    rules = load_prompt_intake_rules(str(ROOT / "config" / "prompt_intake_rules.json"))

    assert "cli" in rules["supported_system_types"]
    assert "файл" in markers("input_markers", rules=rules)
    assert "desktop_gui" in marker_groups("unsupported", rules=rules)
    assert "live_network" in marker_groups("risk", rules=rules)


def test_prompt_intake_rules_reject_unknown_system_type(tmp_path: Path):
    path = tmp_path / "rules.json"
    path.write_text(
        """{
  "schema_version": "prompt_intake_rules.v1",
  "status": "active",
  "supported_system_types": ["cli"],
  "system_type_rules": [{"system_type": "sql_service", "markers": ["sql"]}],
  "dependency_policy_markers": [],
  "input_markers": [],
  "output_markers": [],
  "success_criteria_markers": [],
  "simple_cli_transform_markers": [],
  "scope_unbounded_markers": [],
  "cli_argument_program": {},
  "boundary_marker_groups": {"unsupported": {}, "risk": {}},
  "clarification_questions": {}
}
""",
        encoding="utf-8",
    )

    with pytest.raises(PromptIntakeRulesError, match="supported system types"):
        load_prompt_intake_rules(str(path))
