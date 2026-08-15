from runtime.first_slice_reselection_request import build_first_slice_reselection_request
from runtime.spec_writer_target_binding import promote_environment_ready_candidate


def test_environment_ready_candidate_is_promoted_within_score_slack():
    missing = _ranked("pkg/adapter.py:run", 80, "missing_external")
    ready = _ranked("pkg/core.py:normalize", 55, "ready")

    ranked = promote_environment_ready_candidate([missing, ready])

    assert ranked[0]["source"] == "pkg/core.py:normalize"
    assert "environment-ready candidate selected" in ranked[0]["reasons"][-1]


def test_reselection_request_is_required_without_ready_function_alternative():
    request = build_first_slice_reselection_request(
        {"candidate": "pkg/adapter.py:run"},
        {
            "status": "resolution_required",
            "missing_modules": ["optional_sdk"],
            "ranked_alternatives": [
                {"target": "pkg/other.py:run", "readiness_status": "missing_external"},
                {"target": "pkg/context.py", "readiness_status": "ready"},
            ],
        },
    )

    assert request["status"] == "required"
    assert request["trigger"] == "no_environment_ready_candidate_in_approved_first_slice"
    assert request["authority"] == "architect_reselection_required_no_automatic_scope_expansion"


def _ranked(source: str, score: int, status: str) -> dict:
    return {
        "source": source,
        "score": score,
        "index": 0 if status == "missing_external" else 1,
        "reasons": [],
        "evidence": {"dependency_readiness": {"status": status}},
    }
