from runtime.self_improvement_trials import best_attempt, challenger_sources, trial_conclusion


def test_challengers_prioritize_recommendation_and_exclude_failed_source():
    packet = {
        "artifact_evidence": {
            "technical_spec": {
                "ranked_candidates": [
                    {"source": "app.py:failed"},
                    {"source": "app.py:second"},
                    {"source": "app.py:third"},
                    {"source": "app.py:fourth"},
                ]
            }
        }
    }

    result = challenger_sources(
        {"recommended_source": "app.py:third"},
        packet,
        current_source="app.py:failed",
        limit=2,
    )

    assert result == ["app.py:third", "app.py:second"]


def test_challengers_reject_invented_recommendation():
    packet = {"artifact_evidence": {"technical_spec": {"ranked_candidates": [{"source": "app.py:real"}]}}}

    result = challenger_sources(
        {"recommended_source": "app.py:invented"},
        packet,
        current_source="app.py:failed",
        limit=3,
    )

    assert result == ["app.py:real"]


def test_best_attempt_uses_measured_minimum_not_llm_claim():
    baseline = {"project_min_score": 8.4, "role_scores": {"a": 9.7, "b": 8.4}}
    attempts = [
        {"result": {"project_min_score": 8.8, "role_scores": {"a": 9.7, "b": 8.8}}},
        {"result": {"project_min_score": 9.2, "role_scores": {"a": 9.7, "b": 9.2}}},
    ]

    assert best_attempt(baseline, attempts)["project_min_score"] == 9.2


def test_repeated_flat_target_trials_request_contract_knowledge():
    baseline = {"project_min_score": 8.4}
    attempts = [
        {"parameter_changes": {"spec_writer_candidate_preference": "app.py:a"}, "result": {"project_min_score": 8.4}},
        {"parameter_changes": {"spec_writer_candidate_preference": "app.py:b"}, "result": {"project_min_score": 8.4}},
    ]

    result = trial_conclusion(baseline, attempts)

    assert result["target_search_exhausted"] is True
    assert result["recommended_change_type"] == "staged_kb_contract_profile"
