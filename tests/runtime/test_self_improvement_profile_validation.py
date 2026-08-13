from runtime.self_improvement_profile_validation import build_profile_validation_report


def test_recognition_only_cases_do_not_confirm_treatment():
    candidate = {
        "candidate_id": "kbc_test",
        "proposed_record": {"contract_family": "external_service_state_sync_boundary"},
        "source_cases": [{"project": "weak", "status": "confirmed"}],
    }
    observations = [
        {
            "project": "green_a",
            "recognized_family": "external_service_state_sync_boundary",
            "training_status": "already_at_target",
            "score_delta": 0.0,
        },
        {
            "project": "green_b",
            "recognized_family": "external_service_state_sync_boundary",
            "training_status": "already_at_target",
            "score_delta": 0.0,
        },
    ]

    report = build_profile_validation_report(candidate, observations, target_score=9.7)

    assert report["recognition_case_count"] == 2
    assert report["confirmed_improvement_case_count"] == 1
    assert report["status"] == "collect_more_improvement_cases"


def test_independent_improvements_can_reach_review_gate():
    candidate = {
        "candidate_id": "kbc_test",
        "proposed_record": {"contract_family": "external_service_state_sync_boundary"},
        "source_cases": [{"project": "weak", "status": "confirmed"}],
    }
    observations = [
        {
            "project": name,
            "recognized_family": "external_service_state_sync_boundary",
            "training_status": "confirmed_improvement",
            "score_delta": 0.5,
        }
        for name in ("holdout_a", "holdout_b")
    ]

    report = build_profile_validation_report(candidate, observations, target_score=9.7)

    assert report["confirmed_improvement_case_count"] == 3
    assert report["status"] == "ready_for_review"
