from pathlib import Path

from runtime.self_improvement_hypothesis_context import probe_summary
from runtime.self_improvement_hypothesis_validation import build_validation_plan


def _report(context: bool):
    quality = {"structural_evidence": {
        "observed_side_effects": ["memory_state"],
        "output_inference_basis": "no_value_return",
    }}
    if context:
        quality["contract_archetype_ids"] = ["logging_record_projection"]
    return {
        "project": "source", "knowledge_candidate_path": "candidate.json",
        "diagnosis": {"failure_class": "side_effectful_target"},
        "baseline": {"selected_candidate_quality": quality},
    }


def test_validation_plan_anchors_queries_and_identity_to_measured_contract_context():
    policy = {"hypothesis_holdout": {
        "query_profiles": {"default": ["python library"]},
        "query_composition": {"enabled": True, "maximum_queries": 1},
        "signature_query_terms": {
            "maximum_queries": 3,
            "semantic_context": {
                "logging_record_projection": ["structured logging formatter"],
            },
            "effects": {"memory_state": ["state registry"]},
            "output_bases": {"no_value_return": ["command handler"]},
        },
    }}

    contextual = build_validation_plan([_report(True)], policy)
    generic = build_validation_plan([_report(False)], policy)

    assert contextual["semantic_context"] == ["logging_record_projection"]
    assert contextual["queries"][0] == "structured logging formatter command handler"
    assert contextual["hypothesis_id"] != generic["hypothesis_id"]


def test_probe_context_rejects_same_structure_from_unrelated_contract_family():
    plan = build_validation_plan([_report(True)], {
        "hypothesis_holdout": {"query_profiles": {"default": ["python library"]}},
    })
    matching = _report(True)
    unrelated = _report(False)
    unrelated["baseline"]["selected_candidate_quality"]["contract_archetype_ids"] = [
        "cache_lookup_boundary"
    ]

    assert probe_summary(Path("logging"), matching, plan)["matches_hypothesis"]
    assert not probe_summary(Path("cache"), unrelated, plan)["matches_hypothesis"]
