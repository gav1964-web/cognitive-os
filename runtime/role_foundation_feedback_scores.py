"""Evidence-adjusted scoring for the first three roles."""

from __future__ import annotations

from typing import Any

from .foundation_semantic_quality_policy import load_foundation_semantic_quality_policy
from .role_foundation_trial_status import (
    spec_writer_blocked_no_safe_candidate,
    unresolved_reselection,
)


def role_score_evaluation(result: dict[str, Any]) -> dict[str, Any]:
    local = _local_role_scores(result)
    adjusted = dict(local)
    adjustments: list[dict[str, Any]] = []
    for role, cap, reason in _feedback_caps(result):
        value = adjusted.get(role)
        if value is None or float(value) <= cap:
            continue
        adjusted[role] = round(cap, 2)
        adjustments.append({
            "role": role,
            "local_score": round(float(value), 2),
            "adjusted_score": round(cap, 2),
            "reason": reason,
        })
    return {
        "local_role_scores": local,
        "role_scores": adjusted,
        "adjustments": adjustments,
        "acceptance_signal": _acceptance_signal(result) or "not_measured",
    }


def role_scores(result: dict[str, Any]) -> dict[str, float | None]:
    return dict(role_score_evaluation(result)["role_scores"])


def apply_role_score_caps(scores: dict[str, float | None]) -> dict[str, float | None]:
    caps = dict(load_foundation_semantic_quality_policy().get("role_score_caps") or {})
    return {
        role: min(float(value), float(caps[role])) if value is not None and role in caps else value
        for role, value in scores.items()
    }


def _local_role_scores(result: dict[str, Any]) -> dict[str, float | None]:
    score = dict(result.get("score") or {})
    quality_results = dict(dict(score.get("quality") or {}).get("results") or {})
    project_score = _quality_score(quality_results, "project_map_report")
    if result.get("blocker") in {"scope_selection_required", "no_safe_python_candidate"}:
        project_score = project_score if project_score is not None else _ten_point(score.get("artifact_score"))
        return apply_role_score_caps({"project_analyzer": project_score, "architect": None, "spec_writer": None})

    architect_scores = _available(
        _quality_score(quality_results, "adr"),
        _ten_point(dict(result.get("architect_red_team") or {}).get("score")),
    )
    spec_scores = _available(
        _quality_score(quality_results, "technical_spec"),
        _ten_point(dict(result.get("spec_writer_red_team") or {}).get("score")),
        _semantic_candidate_score(result),
    )
    semantic_scores = dict(dict(result.get("foundation_semantic_quality") or {}).get("role_scores") or {})
    if spec_writer_blocked_no_safe_candidate(result):
        spec_scores = [10.0]
    return apply_role_score_caps({
        "project_analyzer": _minimum(project_score, _number(semantic_scores.get("project_analyzer"))),
        "architect": _minimum(*architect_scores, _number(semantic_scores.get("architect"))),
        "spec_writer": _minimum(*spec_scores, _number(semantic_scores.get("spec_writer"))),
    })


def _feedback_caps(result: dict[str, Any]) -> list[tuple[str, float, str]]:
    policy = dict(load_foundation_semantic_quality_policy().get("feedback_scoring") or {})
    signal = _acceptance_signal(result)
    confirmed = signal in set(policy.get("executable_confirmation_signals") or [])
    rows: list[tuple[str, float, str]] = []
    if not confirmed:
        rows.extend(_cap_rows(policy.get("unverified_handoff_caps"), "no executable downstream confirmation"))
    if signal == "meta_only":
        rows.extend(_cap_rows(policy.get("meta_only_caps"), "downstream acceptance produced meta_only evidence"))
    if not unresolved_reselection(result):
        return rows
    rows.extend(_cap_rows(policy.get("terminal_reselection_caps"), "terminal first-slice reselection"))
    request = _reselection_request(result)
    outcome = dict(request.get("outcome") or {})
    if int(outcome.get("expanded_candidate_count") or 0) == 0:
        rows.extend(_cap_rows(policy.get("no_expanded_candidates_caps"), "Analyzer supplied no expanded executable candidates"))
    if request.get("resolution_status") == "iteration_limit":
        rows.append((
            "architect",
            float(policy.get("iteration_limit_architect_cap") or 6.5),
            "Architect exhausted the reselection iteration budget",
        ))
    return rows


def _cap_rows(value: Any, reason: str) -> list[tuple[str, float, str]]:
    return [(str(role), float(cap), reason) for role, cap in dict(value or {}).items()]


def _acceptance_signal(result: dict[str, Any]) -> str:
    evidence = dict(result.get("downstream_evidence") or {})
    return str(evidence.get("acceptance_signal") or result.get("acceptance_signal") or "")


def _reselection_request(result: dict[str, Any]) -> dict[str, Any]:
    spec = dict(dict(result.get("artifacts") or {}).get("technical_spec") or {})
    return dict(spec.get("first_slice_reselection_request") or {})


def _quality_score(results: dict[str, Any], key: str) -> float | None:
    row = results.get(key)
    return _ten_point(row.get("score")) if isinstance(row, dict) else None


def _semantic_candidate_score(result: dict[str, Any]) -> float | None:
    value = result.get("selected_candidate_quality")
    semantic = _semantic_score(value)
    spec = dict(dict(result.get("artifacts") or {}).get("technical_spec") or {})
    review = dict(dict(spec.get("extraction_contract") or {}).get("semantic_review") or {})
    checks = dict(review.get("checks") or {})
    if review.get("status") == "approved_with_constraints" and checks and all(checks.values()):
        policy = load_foundation_semantic_quality_policy()
        floor = float(dict(policy.get("spec_writer") or {}).get("semantic_review_floor_score") or 9.2)
        semantic = max(semantic or 0.0, floor)
    return semantic


def _semantic_score(value: Any) -> float | None:
    if not isinstance(value, dict) or value.get("score") is None:
        return None
    return round(max(0.0, min(10.0, float(value["score"]) / 10.0)), 2)


def _ten_point(value: Any) -> float | None:
    return None if value is None else round(max(0.0, min(10.0, float(value) * 10.0)), 2)


def _number(value: Any) -> float | None:
    return None if value is None else round(float(value), 2)


def _available(*values: float | None) -> list[float]:
    return [float(value) for value in values if value is not None]


def _minimum(*values: float | None) -> float | None:
    available = _available(*values)
    return round(min(available), 2) if available else None
