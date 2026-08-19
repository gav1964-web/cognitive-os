from runtime.role_foundation_field_trial import _case_status


def test_failed_pipeline_is_not_relabelled_as_controlled_block():
    result = {"status": "failed", "spec_writer_red_team": {"handoff_verdict": "blocked_no_safe_candidate"}}

    assert _case_status(result) == "needs_review"


def test_explicit_block_preserves_controlled_block_status():
    result = {"status": "blocked", "spec_writer_red_team": {"handoff_verdict": "blocked_no_safe_candidate"}}

    assert _case_status(result) == "blocked_ok"
