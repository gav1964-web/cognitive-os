"""Bounded parameter trials for project-driven self-improvement."""

from __future__ import annotations

from typing import Any


def challenger_sources(
    diagnosis: dict[str, Any],
    failure_packet: dict[str, Any],
    *,
    current_source: str,
    limit: int,
) -> list[str]:
    """Return unique, evaluator-discovered sources in diagnostic priority order."""
    evidence = dict(failure_packet.get("artifact_evidence") or {})
    spec = dict(evidence.get("technical_spec") or {})
    ranked = [str(row.get("source") or "") for row in list(spec.get("ranked_candidates") or [])]
    recommended = str(diagnosis.get("recommended_source") or "")
    ordered = ([recommended] if recommended else []) + ranked
    result: list[str] = []
    for source in ordered:
        if not source or source == current_source or source in result or source not in ranked:
            continue
        result.append(source)
        if len(result) >= max(0, limit):
            break
    return result


def best_attempt(baseline: dict[str, Any], attempts: list[dict[str, Any]]) -> dict[str, Any]:
    """Choose by unchanged project score, then by the weakest role and score sum."""
    if not attempts:
        return baseline

    def key(attempt: dict[str, Any]) -> tuple[float, float, float]:
        result = dict(attempt.get("result") or {})
        scores = [float(value) for value in dict(result.get("role_scores") or {}).values() if value is not None]
        return (
            float(result.get("project_min_score") or 0.0),
            min(scores) if scores else 0.0,
            sum(scores),
        )

    return dict(max(attempts, key=key).get("result") or baseline)


def trial_conclusion(baseline: dict[str, Any], attempts: list[dict[str, Any]]) -> dict[str, Any]:
    """Convert repeated measured failures into the next reusable hypothesis."""
    tested = [
        dict(row.get("parameter_changes") or {}).get("spec_writer_candidate_preference")
        for row in attempts
        if dict(row.get("parameter_changes") or {}).get("spec_writer_candidate_preference")
    ]
    deltas = [
        round(float(dict(row.get("result") or {}).get("project_min_score") or 0.0) - float(baseline["project_min_score"]), 2)
        for row in attempts
    ]
    target_search_exhausted = len(tested) >= 2 and not any(delta > 0 for delta in deltas)
    return {
        "tested_candidate_preferences": tested,
        "measured_score_deltas": deltas,
        "target_search_exhausted": target_search_exhausted,
        "next_hypothesis": "missing_reusable_semantic_contract" if target_search_exhausted else "continue_bounded_parameter_search",
        "recommended_change_type": "staged_kb_contract_profile" if target_search_exhausted else "none",
    }
