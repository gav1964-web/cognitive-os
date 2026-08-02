from __future__ import annotations

from runtime.role_spec_writer_ranking import name_and_contract_score
from runtime.target_quality import semantic_target_quality_report
from runtime.target_quality_policy import load_target_quality_policy


def test_target_quality_policy_loads_required_sections():
    policy = load_target_quality_policy()

    assert policy["schema_version"] == "target_quality_policy.v1"
    assert "target_quality" in policy
    assert "spec_writer_ranking" in policy
    assert policy["target_quality"]["suspicious_path_tokens"]
    assert policy["spec_writer_ranking"]["deterministic_shape_tokens"]


def test_target_quality_policy_drives_quality_and_ranking_rules():
    weak = semantic_target_quality_report(
        "pkg/utils/helper.py:version",
        ranked_candidates=["pkg/utils/helper.py:version"],
        source_evidence=["pkg/utils/helper.py:version"],
    )
    strong = semantic_target_quality_report(
        "pkg/core/parser.py:parse_payload",
        ranked_candidates=["pkg/core/parser.py:parse_payload"],
        source_evidence=["pkg/core/parser.py:parse_payload"],
    )
    score, reasons = name_and_contract_score(
        "pkg/core/parser.py:parse_payload",
        {"args": [{"name": "payload", "annotation": "dict"}], "returns": "ParsedPayload"},
        [],
    )

    assert weak["status"] in {"suspicious", "poor"}
    assert strong["status"] == "strong"
    assert score > 0
    assert "deterministic parser" in " ".join(reasons)
