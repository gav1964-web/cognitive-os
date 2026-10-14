from __future__ import annotations

from runtime.project_architecture_synthesis import load_all_knowledge_records
from runtime.role_knowledge import records_for_role, role_knowledge_distribution


def test_role_knowledge_distribution_uses_role_api_defaults():
    records = load_all_knowledge_records()

    distribution = role_knowledge_distribution(records)

    roles = {row["role"]: row for row in distribution["roles"]}
    assert distribution["artifact_type"] == "RoleKnowledgeDistribution"
    assert roles["architect"]["record_count"] > roles["implementer"]["record_count"]
    assert roles["implementer"]["record_types"]["capability_pattern"] >= 40
    assert roles["researcher"]["record_types"]["project_lesson"] >= 5
    assert roles["tester"]["record_types"]["risk_pattern"] > 0
    assert distribution["policy"]["records_are_role_api"] is True


def test_records_for_role_enriches_legacy_records():
    records = [
        {"record_type": "risk_pattern", "risk_id": "r1"},
        {"record_type": "project_archetype_rule", "rule_id": "a1"},
    ]

    reviewer_records = records_for_role(records, "reviewer")

    assert reviewer_records == [
        {
            "record_type": "risk_pattern",
            "risk_id": "r1",
            "role_scope": ["architect", "tester", "reviewer"],
            "evidence_strength": "strong",
        }
    ]


def test_researcher_knowledge_prefers_evidence_over_guessing():
    records = records_for_role(load_all_knowledge_records(), "researcher")
    lessons = {record.get("lesson_id"): record for record in records}

    assert "researcher_gap_packet_not_guess" in lessons
    assert "researcher_llm_is_hypothesis_source" in lessons
    assert lessons["researcher_external_info_as_evidence"]["evidence_strength"] == "medium"


def test_implementer_knowledge_has_greenfield_execution_patterns():
    records = records_for_role(load_all_knowledge_records(), "implementer")
    pattern_ids = {record.get("pattern_id") for record in records}
    lessons = {record.get("lesson_id") for record in records}

    assert "small_project_scaffold" in pattern_ids
    assert "acceptance_test_mapper" in pattern_ids
    assert "implementer_minimal_runnable_first" in lessons
