from __future__ import annotations

from pathlib import Path

import pytest

from runtime.followup_rules import FollowupRulesError, load_followup_rules, markers


ROOT = Path(__file__).resolve().parents[2]


def test_followup_rules_load_external_markers():
    rules = load_followup_rules(str(ROOT / "config" / "followup_rules.json"))

    assert "существует ли" in markers("question_markers", rules=rules)
    assert "убери" in markers("change_markers", rules=rules)


def test_followup_rules_reject_missing_marker_list(tmp_path: Path):
    path = tmp_path / "rules.json"
    path.write_text(
        """{
  "schema_version": "followup_rules.v1",
  "status": "active",
  "question_markers": [],
  "change_markers": [],
  "replacement_action_markers": [],
  "replacement_reference_markers": []
}
""",
        encoding="utf-8",
    )

    with pytest.raises(FollowupRulesError, match="question_markers"):
        load_followup_rules(str(path))
