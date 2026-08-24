from runtime.self_improvement_hypothesis_validation import build_validation_plan
from runtime.self_improvement_signatures import (
    assess_signature_match, diagnosis_envelope, portable_failure_signature, recovery_metrics,
    semantic_context,
)


def test_signature_assessment_keeps_contrast_evidence():
    result = assess_signature_match(
        "side_effectful_target|memory_state|return_expression",
        "side_effectful_target|memory_state|void_side_effect",
        {"effect_match_mode": "required_subset"},
    )

    assert not result["matched"]
    assert result["match_kind"] == "near_contrast"
    assert result["score"] == 0.75


def test_signature_assessment_rejects_forbidden_additional_effect():
    result = assess_signature_match(
        "side_effectful_target|filesystem_write,memory_state|void_side_effect",
        "side_effectful_target|memory_state|void_side_effect",
        {
            "effect_match_mode": "required_subset",
            "forbidden_additional_effects": ["filesystem_write"],
        },
    )

    assert not result["matched"]
    assert result["match_kind"] == "near_contrast"
    assert result["forbidden_additional_effects"] == ["filesystem_write"]


def test_recovery_metrics_separate_target_alignment_from_signature_matching():
    metrics = recovery_metrics([
        {
            "project": "aligned", "matches_hypothesis": True,
            "retrieval_alignment": {"aligned": True},
            "signature_assessment": {"class_match": True},
        },
        {
            "project": "drifted", "matches_hypothesis": False,
            "retrieval_alignment": {"aligned": False},
            "signature_assessment": {"class_match": False},
        },
        {"project": "prior", "matches_hypothesis": True},
    ])

    assert metrics["target_alignment_count"] == 1
    assert metrics["target_alignment_measured_count"] == 2
    assert metrics["target_alignment_rate"] == 0.5
    assert metrics["target_drift_projects"] == ["drifted"]


def test_signature_canonicalizes_llm_failure_class_aliases_without_structural_evidence():
    normalization = {"failure_class_families": {
        "spec_writer_candidate_selection": [
            "spec_contract_unsafe_candidates", "spec_writer_no_safe_candidate",
        ],
    }}
    signatures = {
        portable_failure_signature(
            {"diagnosis": {"failure_class": failure_class}}, normalization
        )
        for failure_class in (
            "spec_writer_candidate_selection", "spec_contract_unsafe_candidates",
            "spec_writer_no_safe_candidate",
        )
    }

    assert signatures == {"spec_writer_candidate_selection|pure|unknown"}


def test_hypothesis_identity_ignores_alias_wording_and_plan_revision():
    normalization = {"failure_class_families": {
        "spec_writer_candidate_selection": ["spec_writer_no_safe_candidate"],
    }}

    def plan(failure_class: str, version: str):
        report = {
            "project": "sample", "knowledge_candidate_path": "candidate.json",
            "diagnosis": {"failure_class": failure_class},
        }
        policy = {"hypothesis_holdout": {
            "plan_version": version, "query_profiles": {"default": ["python library"]},
            "signature_normalization": normalization,
        }}
        return build_validation_plan([report], policy)

    first = plan("spec_writer_no_safe_candidate", "v1")
    second = plan("spec_writer_candidate_selection", "v2")

    assert first["hypothesis_id"] == second["hypothesis_id"]
    assert first["failure_class"] == second["failure_class"]
    assert first["plan_version"] != second["plan_version"]


def test_hypothesis_identity_uses_measured_signature_over_diagnosis_label():
    def plan(failure_class: str):
        report = {
            "project": "sample", "knowledge_candidate_path": "candidate.json",
            "diagnosis": {"failure_class": failure_class},
            "baseline": {"downstream_evidence": {"reason": "meta_only"}},
        }
        policy = {"hypothesis_holdout": {
            "query_profiles": {"default": ["python library"]},
        }}
        return build_validation_plan([report], policy)

    assert plan("dependency_boundary")["hypothesis_id"] == plan(
        "executable_sample_contract"
    )["hypothesis_id"]


def test_diagnosis_envelope_preserves_measured_semantic_context():
    report = {"baseline": {"selected_candidate_quality": {
        "contract_archetype_ids": ["logging_record_projection"],
        "semantic_profile_ids": ["logging_output_format_boundary"],
    }}}

    assert diagnosis_envelope(report)["semantic_context"] == [
        "logging_output_format_boundary", "logging_record_projection",
    ]


def test_semantic_context_separates_executable_failure_families():
    def report(detail: str):
        return {"baseline": {"downstream_evidence": {"summary": {
            "skipped_targets": [{
                "reason": "positive_sample_execution_failed", "detail": detail,
            }],
        }}}}

    assert semantic_context(report("mismatched embedding dimensions (2 != 3)")) == [
        "executable_failure:sample_shape_mismatch",
    ]
    assert semantic_context(report("got _SafeMethodAttribute instead of str")) == [
        "executable_failure:receiver_materialization_mismatch",
    ]
    assert semantic_context(report("unsupported operand type(s) for |: '_StubObject'")) == [
        "executable_failure:dependency_stub_operation_mismatch",
    ]
