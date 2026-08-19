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
