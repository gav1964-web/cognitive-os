import json

from runtime.self_improvement_training import (
    _failure_packet,
    _outcome,
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
