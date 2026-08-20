from unittest.mock import patch

from runtime.local_inference import LocalInferenceConfig
from runtime.self_improvement_analysis import diagnose_training_failure


def _config(model: str) -> LocalInferenceConfig:
    return LocalInferenceConfig(base_url="http://test", model=model, provider_label=model)


def _diagnosis(confidence: float) -> dict:
    return {
        "failure_class": "weak_spec_target",
        "diagnosis": "Spec Writer selected an operational callback.",
        "hypothesis": "Rerank the source-backed domain contract.",
        "confidence": confidence,
        "target_roles": ["spec_writer"],
        "parameter_changes": ["spec_writer_advisory", "score_threshold"],
        "proposed_knowledge": {"rule_id": "prefer_domain_contract"},
        "recommended_source": "service.py:sync_records",
    }


def test_high_confidence_local_diagnosis_avoids_external_teacher():
    with patch("runtime.self_improvement_analysis.call_json_chat", return_value=_diagnosis(0.9)) as mocked:
        result = diagnose_training_failure({}, local_config=_config("local"), teacher_config=_config("teacher"))

    assert mocked.call_count == 1
    assert result["model_trace"]["tier"] == "local_l35"
    assert result["parameter_changes"] == ["spec_writer_advisory"]


def test_low_confidence_local_diagnosis_escalates_once_to_teacher():
    with patch(
        "runtime.self_improvement_analysis.call_json_chat",
        side_effect=[_diagnosis(0.4), _diagnosis(0.92)],
    ) as mocked:
        result = diagnose_training_failure({}, local_config=_config("local"), teacher_config=_config("teacher"))

    assert mocked.call_count == 2
    assert result["model_trace"]["tier"] == "external_teacher"
    assert result["escalated_from"]["model"] == "local"


def test_confident_but_non_actionable_diagnosis_escalates_to_teacher():
    local = _diagnosis(0.95)
    local["recommended_source"] = ""
    local["proposed_knowledge"] = {}
    teacher = _diagnosis(0.9)
    with patch("runtime.self_improvement_analysis.call_json_chat", side_effect=[local, teacher]) as mocked:
        result = diagnose_training_failure({}, local_config=_config("local"), teacher_config=_config("teacher"))

    assert mocked.call_count == 2
    assert result["model_trace"]["tier"] == "external_teacher"


def test_invalid_local_config_proposal_escalates_to_teacher():
    local = _diagnosis(0.95)
    local["proposed_knowledge"] = {"config_mutation_proposal": {
        "artifact_type": "ConfigMutationProposal",
        "target_config": "executable_acceptance_policy.json",
        "operation": "merge_object",
        "path": "/structural_sample_policy",
        "content": {"project.py:handler": {"input_contract": "string"}},
    }}
    teacher = _diagnosis(0.9)
    with patch("runtime.self_improvement_analysis.call_json_chat", side_effect=[local, teacher]) as mocked:
        result = diagnose_training_failure({}, local_config=_config("local"), teacher_config=_config("teacher"))

    assert mocked.call_count == 2
    assert result["model_trace"]["tier"] == "external_teacher"


def test_score_manipulation_hypothesis_is_rejected():
    response = _diagnosis(0.9)
    response["hypothesis"] = "Apply a score boost and recalibrate the threshold."
    with patch("runtime.self_improvement_analysis.call_json_chat", return_value=response):
        result = diagnose_training_failure({}, local_config=_config("local"))

    assert result["status"] == "failed"
    assert "score_manipulation" in result["policy_violations"]


def test_non_object_proposed_knowledge_does_not_crash_training():
    response = _diagnosis(0.9)
    response["proposed_knowledge"] = ["not", "an", "object"]
    with patch("runtime.self_improvement_analysis.call_json_chat", return_value=response):
        result = diagnose_training_failure({}, local_config=_config("local"))

    assert result["status"] == "ok"
    assert result["proposed_knowledge"] == {}


def test_current_failed_target_is_not_an_actionable_recommendation():
    response = _diagnosis(0.9)
    response["recommended_source"] = "signals.py:on_done"
    with patch("runtime.self_improvement_analysis.call_json_chat", side_effect=[response, response]):
        result = diagnose_training_failure(
            {"selected_candidate": "signals.py:on_done"},
            local_config=_config("local"),
            teacher_config=_config("teacher"),
        )

    assert result["status"] == "failed"
    assert "same_as_failed_target" in result["policy_violations"]


def test_empty_recommendation_is_valid_when_no_candidate_was_selected():
    response = _diagnosis(0.9)
    response["recommended_source"] = ""
    with patch("runtime.self_improvement_analysis.call_json_chat", return_value=response):
        result = diagnose_training_failure(
            {"selected_candidate": None},
            local_config=_config("local"),
        )

    assert result["status"] == "ok"
    assert "same_as_failed_target" not in result["policy_violations"]


def test_observed_acceptance_reason_canonicalizes_free_form_failure_class():
    response = _diagnosis(0.9)
    response["failure_class"] = "transport/context errors"
    packet = {
        "downstream_evidence": {
            "status": "passed",
            "acceptance_signal": "meta_only",
            "summary": {"skipped_reason_counts": {"positive_sample_execution_failed": 1}},
        }
    }
    with patch("runtime.self_improvement_analysis.call_json_chat", return_value=response):
        result = diagnose_training_failure(packet, local_config=_config("local"))

    assert result["failure_class"] == "executable_sample_contract"
    assert result["llm_failure_class"] == "transport/context errors"


def test_missing_import_is_canonical_dependency_boundary():
    response = _diagnosis(0.9)
    response["failure_class"] = "dependency_management"
    packet = {"downstream_evidence": {"summary": {
        "skipped_reason_counts": {"import_failed_missing_module": 1},
    }}}
    with patch("runtime.self_improvement_analysis.call_json_chat", return_value=response):
        result = diagnose_training_failure(packet, local_config=_config("local"))

    assert result["failure_class"] == "dependency_boundary"
