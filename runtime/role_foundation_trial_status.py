"""Conservative status interpretation for foundation field trials."""

from __future__ import annotations

from typing import Any


def case_status(result: dict[str, Any]) -> str:
    if unresolved_reselection(result):
        if evidence_bound_exhaustion(result):
            return "blocked_ok"
        return "needs_review"
    if result.get("status") == "ok":
        return "ok"
    if result.get("status") == "blocked" and spec_writer_blocked_no_safe_candidate(result):
        return "blocked_ok"
    if result.get("status") == "blocked" and result.get("blocker") in {
        "scope_selection_required",
        "no_safe_python_candidate",
    }:
        return "blocked_ok"
    return "needs_review"


def unresolved_reselection(result: dict[str, Any]) -> bool:
    spec = dict(dict(result.get("artifacts") or {}).get("technical_spec") or {})
    request = dict(spec.get("first_slice_reselection_request") or {})
    return bool(
        request.get("status") == "required"
        and (
            request.get("terminal") is True
            or request.get("resolution_status") in {"exhausted", "iteration_limit"}
        )
    )


def spec_writer_blocked_no_safe_candidate(result: dict[str, Any]) -> bool:
    return dict(result.get("spec_writer_red_team") or {}).get("handoff_verdict") == "blocked_no_safe_candidate"


def evidence_bound_exhaustion(result: dict[str, Any]) -> bool:
    spec = dict(dict(result.get("artifacts") or {}).get("technical_spec") or {})
    request = dict(spec.get("first_slice_reselection_request") or {})
    outcome = dict(request.get("outcome") or {})
    return bool(
        request.get("resolution_status") == "exhausted"
        and outcome.get("status") == "exhausted"
        and outcome.get("authority") == "architect"
        and int(outcome.get("expanded_candidate_count") or 0) > 0
        and "environment_ready_candidate_count" in outcome
        and "candidate_viability" in outcome
        and int(outcome.get("semantic_qualified_candidate_count") or 0) == 0
        and not list(outcome.get("selected_targets") or [])
    )
