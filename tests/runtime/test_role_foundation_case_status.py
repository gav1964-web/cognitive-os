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


def test_evidence_bound_exhaustion_does_not_require_impossible_execution_confirmation():
    result = {
        "score": {"quality": {"results": {
            "project_map_report": {"score": 100},
            "adr": {"score": 100},
            "technical_spec": {"score": 100},
        }}},
        "architect_red_team": {"score": 100},
        "spec_writer_red_team": {"score": 100},
        "foundation_semantic_quality": {
            "role_scores": {"project_analyzer": 10.0, "architect": 10.0, "spec_writer": 10.0}
        },
        "artifacts": {"technical_spec": {
            "extraction_contract": {"status": "blocked_no_safe_candidate", "candidate": None},
            "first_slice_reselection_request": {
                "status": "required", "terminal": True, "resolution_status": "exhausted",
                "outcome": {
                    "status": "exhausted", "authority": "architect",
                    "expanded_candidate_count": 12, "environment_ready_candidate_count": 7,
                    "candidate_viability": [], "semantic_qualified_candidate_count": 0,
                    "selected_targets": [],
                },
            },
        }},
    }

    evaluation = role_score_evaluation(result)

    assert evaluation["role_scores"] == {
        "project_analyzer": 9.7,
        "architect": 9.7,
        "spec_writer": 9.8,
    }
    assert evaluation["adjustments"] == []


def test_proven_scope_selection_stop_does_not_require_downstream_execution():
    result = {
        "blocker": "scope_selection_required",
        "score": {
            "artifact_score": 1.0,
            "checks": {
                "project_map_report_present": True,
                "scope_selection_report_present": True,
                "scope_selection_blocks_downstream": True,
                "scope_selection_has_candidates_or_damaged_stop": True,
                "adr_not_built": True,
                "technical_spec_not_built": True,
            },
        },
        "scope_selection_report": {
            "status": "blocked_until_scope_selected",
            "preferred_candidate": None,
            "candidate_roots": [{"path": "current-a"}, {"path": "current-b"}],
        },
        "safety": {
            "source_code_changes": False,
            "registry_changes": False,
        },
    }

    evaluation = role_score_evaluation(result)

    assert evaluation["role_scores"] == {
        "project_analyzer": 9.7,
        "architect": None,
        "spec_writer": None,
    }
    assert evaluation["adjustments"] == []


def test_unproven_scope_selection_stop_keeps_feedback_cap():
    result = {
        "blocker": "scope_selection_required",
        "score": {"artifact_score": 1.0, "checks": {}},
        "scope_selection_report": {
            "status": "blocked_until_scope_selected",
            "candidate_roots": [{"path": "only-one"}],
        },
        "safety": {"source_code_changes": False, "registry_changes": False},
    }

    assert role_score_evaluation(result)["role_scores"]["project_analyzer"] == 9.2


def test_unproven_exhaustion_keeps_unverified_handoff_caps():
    result = {
        "foundation_semantic_quality": {
            "role_scores": {"project_analyzer": 10.0, "architect": 10.0, "spec_writer": 10.0}
        },
        "artifacts": {"technical_spec": {
            "extraction_contract": {"status": "blocked_no_safe_candidate", "candidate": None},
            "first_slice_reselection_request": {
                "status": "required", "terminal": True, "resolution_status": "exhausted",
                "outcome": {"status": "exhausted", "expanded_candidate_count": 12},
            },
        }},
    }

    evaluation = role_score_evaluation(result)

    assert evaluation["role_scores"] == {
        "project_analyzer": 8.8,
        "architect": 7.2,
        "spec_writer": 5.0,
    }


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


def test_matching_executable_confirmation_lifts_strong_spec_candidate_to_9_7():
    result = {
        "selected_extraction_candidate": "app.py:project_rows",
        "selected_candidate_quality": {"score": 96, "status": "strong"},
        "foundation_semantic_quality": {
            "role_scores": {"spec_writer": 10.0},
            "checks": {"spec_writer": [
                {"code": "candidate_ranked_first", "passed": True},
                {"code": "io_contract_shapes_specific", "passed": True},
            ]},
        },
        "downstream_evidence": {
            "status": "passed",
            "acceptance_signal": "executable_callable",
            "target": "app.py:project_rows",
            "source_code_changes": False,
        },
    }

    assert role_score_evaluation(result)["role_scores"]["spec_writer"] == 9.7


def test_executable_confirmation_for_other_target_does_not_lift_spec_score():
    result = {
        "selected_extraction_candidate": "app.py:project_rows",
        "selected_candidate_quality": {"score": 96, "status": "strong"},
        "foundation_semantic_quality": {
            "role_scores": {"spec_writer": 10.0},
            "checks": {"spec_writer": [
                {"code": "candidate_ranked_first", "passed": True},
            ]},
        },
        "downstream_evidence": {
            "status": "passed",
            "acceptance_signal": "executable_callable",
            "target": "app.py:other",
            "source_code_changes": False,
        },
    }

    assert role_score_evaluation(result)["role_scores"]["spec_writer"] == 9.6


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
