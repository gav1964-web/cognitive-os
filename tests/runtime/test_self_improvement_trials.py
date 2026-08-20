from runtime.self_improvement_trials import (
    best_attempt,
    challenger_sources,
    finalize_profile_conclusion,
    trial_conclusion,
)


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


def test_challengers_skip_candidates_that_cannot_change_measured_outcome():
    packet = {"artifact_evidence": {"technical_spec": {"ranked_candidates": [
        {"source": "models.py:total", "reasons": ["property accessor is state evidence, not a meaningful first slice"]},
        {"source": "service.py:save", "reasons": ["execution cost requires reselection: persistence_mutation"]},
        {"source": "service.py:normalize", "reasons": ["bounded deterministic transform"]},
    ]}}}

    result = challenger_sources({}, packet, current_source="app.py:failed", limit=3)

    assert result == ["service.py:normalize"]


def test_challengers_allow_callable_read_only_context_but_not_module_script():
    packet = {"artifact_evidence": {"technical_spec": {"ranked_candidates": [
        {"source": "data.py:paths", "kind": "function", "reasons": ["read-only context candidate retained"]},
        {"source": "settings.py", "kind": "module_script", "reasons": ["read-only context candidate retained"]},
    ]}}}

    result = challenger_sources({}, packet, current_source="app.py:failed", limit=3)

    assert result == ["data.py:paths"]


def test_best_attempt_uses_measured_minimum_not_llm_claim():
    baseline = {"project_min_score": 8.4, "role_scores": {"a": 9.7, "b": 8.4}}
    attempts = [
        {"result": {"project_min_score": 8.8, "role_scores": {"a": 9.7, "b": 8.8}}},
        {"result": {"project_min_score": 9.2, "role_scores": {"a": 9.7, "b": 9.2}}},
    ]

    assert best_attempt(baseline, attempts)["project_min_score"] == 9.2


def test_best_attempt_keeps_baseline_when_every_trial_regresses():
    baseline = {"project_min_score": 8.8, "role_scores": {"a": 9.2, "b": 8.8}}
    attempts = [
        {"result": {"project_min_score": 7.5, "role_scores": {"a": 9.2, "b": 7.5}}},
        {"result": {"project_min_score": 6.4, "role_scores": {"a": 8.3, "b": 6.4}}},
    ]

    assert best_attempt(baseline, attempts) == baseline


def test_unapplied_preference_cannot_confirm_improvement_or_exhaust_search():
    baseline = {"project_min_score": 7.5, "role_scores": {"spec_writer": 7.5}}
    attempts = [{
        "parameter_applied": False,
        "parameter_changes": {"spec_writer_candidate_preference": "api.py:requested"},
        "result": {"project_min_score": 9.7, "role_scores": {"spec_writer": 9.7}},
    }]

    assert best_attempt(baseline, attempts) == baseline
    conclusion = trial_conclusion(baseline, attempts)
    assert conclusion["tested_candidate_preferences"] == []
    assert conclusion["target_search_exhausted"] is False


def test_repeated_flat_target_trials_request_contract_knowledge():
    baseline = {"project_min_score": 8.4}
    attempts = [
        {"parameter_changes": {"spec_writer_candidate_preference": "app.py:a"}, "result": {"project_min_score": 8.4}},
        {"parameter_changes": {"spec_writer_candidate_preference": "app.py:b"}, "result": {"project_min_score": 8.4}},
    ]

    result = trial_conclusion(baseline, attempts)

    assert result["target_search_exhausted"] is True
    assert result["recommended_change_type"] == "staged_kb_contract_profile"


def test_no_viable_challengers_stages_capability_gap_without_trials():
    result = trial_conclusion(
        {"project_min_score": 8.8}, [], no_viable_challengers=True
    )

    assert result["target_search_exhausted"] is True
    assert result["next_hypothesis"] == "no_viable_executable_candidate"
    assert result["recommended_change_type"] == "staged_capability_gap"


def test_missing_contract_profile_becomes_capability_gap():
    conclusion = {
        "next_hypothesis": "missing_reusable_semantic_contract",
        "recommended_change_type": "staged_kb_contract_profile",
    }

    result = finalize_profile_conclusion(conclusion, None)

    assert result["recommended_change_type"] == "staged_capability_gap"
    assert result["profile_discovery_status"] == "no_supported_profile"
