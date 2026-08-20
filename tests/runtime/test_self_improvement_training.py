import json

from runtime.local_inference import LocalInferenceConfig
from runtime.self_improvement_experience import generalized_profile_record, stage_training_experience
from runtime.self_improvement_training import (
    _failure_packet,
    _outcome,
    _run_training_attempts,
    _source_fingerprint,
    _validate_recommended_source,
)


def test_no_write_cli_contract_keeps_evidence_requirement_explicit():
    source = open("tools/self_improvement_train.py", encoding="utf-8").read()

    assert "verified role evidence is still written" in source


def _case(score: float) -> dict:
    return {
        "status": "ok",
        "project_min_score": score,
        "role_scores": {"project_analyzer": 9.7, "architect": 9.7, "spec_writer": score},
    }


def test_training_confirms_score_improvement_without_role_regression():
    result = _outcome(_case(8.4), _case(9.2), 9.7)

    assert result["status"] == "confirmed_improvement"
    assert result["score_delta"] == 0.8
    assert result["target_reached"] is False


def test_training_rejects_improvement_when_source_project_changed():
    result = _outcome(_case(8.4), _case(9.7), 9.7, source_changed=True)

    assert result["status"] == "hypothesis_not_confirmed"
    assert result["source_project_changed"] is True


def test_source_fingerprint_tracks_python_source_changes(tmp_path):
    source = tmp_path / "app.py"
    source.write_text("VALUE = 1\n", encoding="utf-8")
    before = _source_fingerprint(tmp_path)
    source.write_text("VALUE = 2\n", encoding="utf-8")

    assert _source_fingerprint(tmp_path) != before


def test_failure_packet_stays_within_local_diagnostician_budget():
    case = {
        **_case(8.4),
        "selected_candidate_quality": {"target": "app.py:run", "score": 84, "reasons": ["x" * 1000] * 20},
        "artifacts": {},
        "warnings": [],
    }

    packet = _failure_packet(case, 9.7)

    assert len(json.dumps(packet, ensure_ascii=False)) <= 6000


def test_training_rejects_recommended_source_outside_ranked_candidates():
    diagnosis = {"recommended_source": "invented.py:run", "policy_violations": []}
    baseline = {**_case(8.4), "artifacts": {}, "warnings": []}

    result = _validate_recommended_source(diagnosis, baseline)

    assert result["recommended_source"] == ""
    assert "recommended_source_outside_bounded_candidates" in result["policy_violations"]


def test_training_rejects_current_failed_source_as_challenger():
    diagnosis = {"recommended_source": "app.py:run", "policy_violations": []}
    baseline = {
        **_case(8.4),
        "selected_extraction_candidate": "app.py:run",
        "artifacts": {},
        "warnings": [],
    }

    result = _validate_recommended_source(diagnosis, baseline)

    assert result["recommended_source"] == ""
    assert "same_as_failed_target" in result["policy_violations"]


def test_training_skips_advisory_when_recommended_challenger_is_not_viable(tmp_path):
    attempts = _run_training_attempts(
        tmp_path,
        tmp_path,
        _case(8.8),
        {"recommended_source": "models.py:property", "target_roles": ["architect", "spec_writer"]},
        LocalInferenceConfig(base_url="http://local", model="test"),
        9.7,
        [],
    )

    assert attempts == []


def test_generalized_profile_record_drops_project_specific_selector():
    profile = {
        "id": "training_123",
        "contract_family": "external_service_state_sync_boundary",
        "symbols": ["sync_telegram"],
        "path_contains_any": ["app/integrations/telegram.py"],
        "input_contract": {"request": "Request"},
        "output_contract": {"result": "Result"},
        "side_effect_policy": {"external_io": "explicit"},
        "validation_gates": ["failure is bounded"],
        "failure_modes": ["external_failure"],
        "training_evidence": {"external_io": True, "structured_result": True},
    }

    result = generalized_profile_record(profile)

    assert result["id"] == "external_service_state_sync_boundary"
    assert "symbols" not in result
    assert "path_contains_any" not in result
    assert result["numeric_bonus_from_training"] is False
    assert result["recognition_policy"]["recognizer"] == "external_service_state_sync_boundary"
    assert "symbol_prefixes" not in result["recognition_policy"]


def test_generalized_profile_preserves_portable_family_bindings():
    profile = {
        "contract_family": "persistence_append_command",
        "input_contract": {"unit_of_work": "Session", "record_data": "RecordInput"},
        "input_bindings": {"unit_of_work": ["session"], "record_data": ["*remaining"]},
        "output_contract": {"result": "VoidPersistenceCommand"},
        "side_effect_policy": {"declared": ["database"]},
        "validation_gates": ["append is covered"],
        "failure_modes": ["append_rejected"],
        "training_evidence": {"append_call": True},
    }

    result = generalized_profile_record(profile)

    assert result["input_bindings"] == profile["input_bindings"]
    assert result["recognition_policy"]["required_evidence"] == ["append_call"]


def test_profile_candidate_keeps_project_paths_only_in_provenance(tmp_path):
    profile = {
        "contract_family": "external_service_state_sync_boundary",
        "input_contract": {"request": "Request"},
        "output_contract": {"result": "Result"},
        "side_effect_policy": {"external_io": "explicit"},
        "validation_gates": ["failure is bounded"],
        "failure_modes": ["external_failure"],
        "training_evidence": {"external_io": True},
    }
    attempts = [{"parameter_changes": {"temporary_semantic_profile": profile}, "profile_score_delta": 1.3}]
    path = stage_training_experience(
        tmp_path,
        tmp_path / "private_project",
        {"failure_class": "target_selection", "hypothesis": "private/path.py:sync_private"},
        {"project_min_score": 8.4},
        {"project_min_score": 9.7},
        {"status": "confirmed_improvement"},
        attempts,
        {
            "target_search_exhausted": True,
            "tested_candidate_preferences": ["private/path.py:sync_private"],
            "semantic_profile_trial": {"profile_id": "private_hash", "score_delta": 1.3},
        },
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    proposed = json.dumps(payload["proposed_record"])

    assert "private/path.py" not in proposed
    assert "private_hash" not in proposed
    assert payload["source_cases"][0]["project"] == "private_project"


def test_profile_trial_sources_include_failed_current_target(monkeypatch, tmp_path):
    captured = {}

    def fake_trial(project_dir, sources, evaluate):
        captured["sources"] = sources
        return None

    monkeypatch.setattr("runtime.self_improvement_training.run_profile_trial", fake_trial)
    from runtime.self_improvement_training import _run_contract_profile_attempt

    _run_contract_profile_attempt(
        tmp_path,
        tmp_path,
        {"selected_extraction_candidate": "app.py:allowed_file", "role_scores": {}},
        {},
        LocalInferenceConfig(base_url="http://local", model="test"),
        9.7,
        ["app.py:other"],
        {"target_search_exhausted": True},
    )

    assert captured["sources"] == ["app.py:allowed_file", "app.py:other"]


def test_zero_delta_profile_is_not_staged_as_contract_template(tmp_path):
    profile = {
        "contract_family": "persistence_append_command",
        "input_contract": {"record": "Record"},
        "output_contract": {"result": "Void"},
        "side_effect_policy": {"database_write": "explicit"},
        "validation_gates": ["append is covered"],
        "failure_modes": ["append_failed"],
        "training_evidence": {"append_call": True},
    }
    path = stage_training_experience(
        tmp_path,
        tmp_path / "project",
        {"proposed_knowledge": {"label": "target selection"}},
        {"project_min_score": 9.0},
        {"project_min_score": 9.7},
        {"status": "confirmed_improvement"},
        [{"parameter_changes": {"temporary_semantic_profile": profile}, "profile_score_delta": 0.0}],
        {"target_search_exhausted": True},
    )

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["record_type"] == "role_training_experience"


def test_no_viable_candidate_is_staged_as_portable_capability_gap(tmp_path):
    path = stage_training_experience(
        tmp_path,
        tmp_path / "private_project",
        {
            "failure_class": "target_selection",
            "hypothesis": "private_project has no usable target",
            "target_roles": ["architect", "spec_writer"],
        },
        {"project_min_score": 8.8},
        {"project_min_score": 8.8},
        {"status": "hypothesis_not_confirmed"},
        [],
        {
            "recommended_change_type": "staged_capability_gap",
            "next_hypothesis": "no_viable_executable_candidate",
        },
    )

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["record_type"] == "foundation_capability_gap"
    assert payload["proposed_record"]["gap_id"] == "target_selection:no_viable_executable_candidate"
    assert "private_project" not in payload["proposed_record"]["gap_id"]
