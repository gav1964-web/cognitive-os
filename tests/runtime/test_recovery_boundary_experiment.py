from runtime.recovery_boundary_experiment import evaluate_recovery_boundary_experiments


def _research():
    return {
        "hypotheses": [{
            "cluster": "request_mapping_inside_network_boundary",
            "boundary_contract": {
                "pure_candidate": "build_request_payload",
                "effect_adapter": "transport_request",
                "preserve": ["authentication", "timeouts", "retry_policy", "request_encoding"],
            },
            "next_experiment": {"minimum_reviewed_projects": 2},
        }]
    }


def test_boundary_experiment_stays_blocked_without_evidence() -> None:
    report = evaluate_recovery_boundary_experiments(_research())

    assert report["status"] == "evidence_required"
    assert report["architect_gate"]["developer_handoff_allowed"] is False
    assert report["experiments"][0]["developer_request"] is None


def test_boundary_experiment_admits_only_independent_differential_evidence() -> None:
    invariants = ["authentication", "timeouts", "retry_policy", "request_encoding"]
    cases = [
        {
            "cluster": "request_mapping_inside_network_boundary",
            "project": f"project-{index}",
            "lineage": f"lineage-{index}",
            "holdout": index == 2,
            "source_review_confirmed": True,
            "data_direction_confirmed": True,
            "success_fixture_passed": True,
            "failure_fixture_passed": True,
            "preserved_invariants": invariants,
        }
        for index in (1, 2)
    ]

    report = evaluate_recovery_boundary_experiments(_research(), evidence_cases=cases)

    assert report["status"] == "admitted"
    assert report["architect_gate"]["automatic_admission"] is False
    assert report["architect_gate"]["developer_handoff_allowed"] is True
