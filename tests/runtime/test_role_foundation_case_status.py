from runtime.role_foundation_feedback_scores import role_score_evaluation
from runtime.role_foundation_field_trial import _case_status, _role_scores


def test_failed_pipeline_is_not_relabelled_as_controlled_block():
    result = {"status": "failed", "spec_writer_red_team": {"handoff_verdict": "blocked_no_safe_candidate"}}

    assert _case_status(result) == "needs_review"


def test_explicit_block_preserves_controlled_block_status():
    result = {"status": "blocked", "spec_writer_red_team": {"handoff_verdict": "blocked_no_safe_candidate"}}

    assert _case_status(result) == "blocked_ok"


def test_terminal_reselection_is_not_reported_as_ready_handoff():
    result = {
        "status": "ok",
        "artifacts": {
            "technical_spec": {
                "first_slice_reselection_request": {
                    "status": "required",
                    "terminal": True,
                    "resolution_status": "exhausted",
                }
            }
        },
    }

    assert _case_status(result) == "needs_review"


def test_evidence_bound_exhaustion_is_a_controlled_block():
    result = {
        "status": "ok",
        "artifacts": {"technical_spec": {"first_slice_reselection_request": {
            "status": "required", "terminal": True, "resolution_status": "exhausted",
            "outcome": {
                "status": "exhausted", "authority": "architect", "expanded_candidate_count": 12,
                "environment_ready_candidate_count": 7, "candidate_viability": [],
                "semantic_qualified_candidate_count": 0, "selected_targets": [],
            },
        }}},
    }

    assert _case_status(result) == "blocked_ok"


def test_terminal_reselection_caps_spec_writer_score():
    result = {
        "score": {"quality": {"results": {"technical_spec": {"score": 100}}}},
        "selected_candidate_quality": {"score": 100, "status": "strong"},
        "spec_writer_red_team": {"score": 100},
        "foundation_semantic_quality": {"role_scores": {"spec_writer": 10.0}},
        "artifacts": {
            "technical_spec": {
                "first_slice_reselection_request": {
                    "status": "required",
                    "terminal": True,
                    "resolution_status": "iteration_limit",
                }
            }
        },
    }

    assert _role_scores(result)["spec_writer"] == 5.0


def test_terminal_reselection_backpropagates_to_upstream_roles():
    result = {
        "score": {
            "quality": {
                "results": {
                    "project_map_report": {"score": 100},
                    "adr": {"score": 100},
                    "technical_spec": {"score": 100},
                }
            }
        },
        "architect_red_team": {"score": 100},
        "spec_writer_red_team": {"score": 100},
        "selected_candidate_quality": {"score": 100},
        "foundation_semantic_quality": {
            "role_scores": {"project_analyzer": 10.0, "architect": 10.0, "spec_writer": 10.0}
        },
        "artifacts": {
            "technical_spec": {
                "first_slice_reselection_request": {
                    "status": "required",
                    "terminal": True,
                    "resolution_status": "iteration_limit",
                    "outcome": {"expanded_candidate_count": 12},
                }
            }
        },
    }

    evaluation = role_score_evaluation(result)

    assert evaluation["local_role_scores"] == {
        "project_analyzer": 9.7,
        "architect": 9.7,
        "spec_writer": 9.8,
    }
    assert evaluation["role_scores"] == {
        "project_analyzer": 8.8,
        "architect": 6.5,
        "spec_writer": 5.0,
    }


def test_executable_callable_preserves_published_role_caps():
    result = {
        "foundation_semantic_quality": {
            "role_scores": {"project_analyzer": 10.0, "architect": 10.0, "spec_writer": 10.0}
        },
        "downstream_evidence": {"acceptance_signal": "executable_callable"},
    }

    assert role_score_evaluation(result)["role_scores"] == {
        "project_analyzer": 9.7,
        "architect": 9.7,
        "spec_writer": 9.8,
    }


def test_matching_executable_confirmation_resolves_prior_reselection():
    result = {
        "status": "ok",
        "selected_extraction_candidate": "app.py:normalize",
        "foundation_semantic_quality": {
            "role_scores": {"project_analyzer": 10.0, "architect": 10.0, "spec_writer": 10.0}
        },
        "artifacts": {"technical_spec": {
            "first_slice_reselection_request": {
                "status": "required", "terminal": True, "resolution_status": "iteration_limit",
            },
        }},
        "downstream_evidence": {
            "status": "passed", "acceptance_signal": "executable_callable",
            "target": "app.py:normalize", "source_code_changes": False,
        },
    }

    assert _case_status(result) == "ok"
    assert role_score_evaluation(result)["role_scores"] == {
        "project_analyzer": 9.7, "architect": 9.7, "spec_writer": 9.8,
    }


def test_executable_confirmation_for_different_target_does_not_resolve_reselection():
    result = {
        "status": "ok",
        "selected_extraction_candidate": "app.py:write",
        "artifacts": {"technical_spec": {"first_slice_reselection_request": {
            "status": "required", "terminal": True, "resolution_status": "iteration_limit",
        }}},
        "downstream_evidence": {
            "status": "passed", "acceptance_signal": "executable_callable",
            "target": "app.py:normalize", "source_code_changes": False,
        },
    }

    assert _case_status(result) == "needs_review"
