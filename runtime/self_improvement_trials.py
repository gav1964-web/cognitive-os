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
    ranked_rows = list(spec.get("ranked_candidates") or [])
    ranked = [
        str(row.get("source") or "") for row in ranked_rows
        if not _candidate_trial_blockers(dict(row or {}))
    ]
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


def _candidate_trial_blockers(candidate: dict[str, Any]) -> list[str]:
    text = " ".join(str(item).lower() for item in candidate.get("reasons", []))
    blockers = {
        "property_accessor": "property accessor is state evidence",
        "write_operation": "write/update/delete operation is side-effect evidence",
        "runtime_dependency": "runtime environment misses external imports",
        "execution_cost": "execution cost requires reselection",
    }
    result = [code for code, token in blockers.items() if token in text]
    if "read-only context candidate retained" in text and candidate.get("kind") == "module_script":
        result.append("read_only_context")
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

    candidates = [{"result": baseline}, *[row for row in attempts if row.get("parameter_applied") is not False]]
    return dict(max(candidates, key=key).get("result") or baseline)


def trial_conclusion(
    baseline: dict[str, Any], attempts: list[dict[str, Any]], *, no_viable_challengers: bool = False
) -> dict[str, Any]:
    """Convert repeated measured failures into the next reusable hypothesis."""
    tested = [
        dict(row.get("parameter_changes") or {}).get("spec_writer_candidate_preference")
        for row in attempts
        if row.get("parameter_applied") is not False
        and dict(row.get("parameter_changes") or {}).get("spec_writer_candidate_preference")
    ]
    deltas = [
        round(float(dict(row.get("result") or {}).get("project_min_score") or 0.0) - float(baseline["project_min_score"]), 2)
        for row in attempts if row.get("parameter_applied") is not False
    ]
    target_search_exhausted = no_viable_challengers or (len(tested) >= 2 and not any(delta > 0 for delta in deltas))
    no_viable = target_search_exhausted and no_viable_challengers
    return {
        "tested_candidate_preferences": tested,
        "measured_score_deltas": deltas,
        "target_search_exhausted": target_search_exhausted,
        "next_hypothesis": (
            "no_viable_executable_candidate" if no_viable else
            "missing_reusable_semantic_contract" if target_search_exhausted else "continue_bounded_parameter_search"
        ),
        "recommended_change_type": (
            "staged_capability_gap" if no_viable else "staged_kb_contract_profile" if target_search_exhausted else "none"
        ),
    }


def finalize_profile_conclusion(
    conclusion: dict[str, Any], profile_attempt: dict[str, Any] | None
) -> dict[str, Any]:
    result = dict(conclusion)
    if profile_attempt is None and result.get("recommended_change_type") == "staged_kb_contract_profile":
        result["recommended_change_type"] = "staged_capability_gap"
        result["profile_discovery_status"] = "no_supported_profile"
    return result
