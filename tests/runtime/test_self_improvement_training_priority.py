from runtime.self_improving_foundation_trial import _training_priority


POLICY = {
    "actionable_acceptance_signals": ["meta_only"],
    "actionable_downstream_statuses": ["failed"],
}


def test_measured_acceptance_failure_precedes_unclassified_lower_status():
    measurable = {
        "project": "parser", "status": "ok", "project_min_score": 7.5,
        "downstream_evidence": {"status": "passed", "acceptance_signal": "meta_only"},
    }
    unknown = {
        "project": "formatter", "status": "needs_review", "project_min_score": 5.0,
    }

    assert _training_priority(measurable, POLICY) < _training_priority(unknown, POLICY)


def test_existing_status_and_score_order_remains_within_same_evidence_tier():
    blocked = {"project": "blocked", "status": "blocked_ok", "project_min_score": 9.2}
    low = {"project": "low", "status": "ok", "project_min_score": 7.5}

    assert _training_priority(blocked, POLICY) < _training_priority(low, POLICY)
