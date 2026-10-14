"""Controlled intake and admission route for unknown project archetypes."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from .knowledge_admission import build_kb_candidate
from .research_loop import build_knowledge_gap_packet, build_research_plan


def build_unknown_project_lifecycle(
    classification_debt: dict[str, Any], *, policy: dict[str, Any]
) -> dict[str, Any]:
    """Turn classification debt into bounded research and staged KB candidates."""
    lifecycle_policy = dict(policy.get("unknown_archetype_lifecycle") or {})
    minimum_cases = int(lifecycle_policy.get("minimum_confirmed_projects") or 3)
    minimum_confidence = float(lifecycle_policy.get("minimum_evidence_confidence") or 0.7)
    minimum_lineages = int(lifecycle_policy.get("minimum_independent_lineages") or 2)
    minimum_digests = int(lifecycle_policy.get("minimum_unique_evidence_digests") or minimum_cases)
    minimum_markers = int(lifecycle_policy.get("minimum_candidate_markers") or 2)
    candidate_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    intakes = []

    for item in classification_debt.get("items", []):
        project = str(item.get("project") or "unknown-project")
        hypotheses = [
            dict(row) for row in item.get("archetype_hypotheses", [])
            if isinstance(row, dict) and row.get("hypothesis_id")
        ]
        gap = build_knowledge_gap_packet(
            question=f"Which reusable project archetype best describes {project}?",
            needed_for="project-stratum classification and role routing",
            role="researcher",
            reason="no configured stratum matched authoritative local evidence",
            acceptable_sources=["official_docs_fetch", "github_repository_search", "user_clarification"],
            confidence_required=minimum_confidence,
            decision_if_unresolved="Keep the project quarantined as unknown_new_archetype.",
        )
        plan = build_research_plan(gap, query_hint=f"{project} architecture project type")
        intakes.append({
            "artifact_type": "UnknownProjectIntake",
            "project": project,
            "status": "provisional" if hypotheses else "research_required",
            "classification_reason": item.get("reason"),
            "observed_signals": sorted(set(
                list(item.get("project_archetypes") or [])
                + list(item.get("contract_families") or [])
            )),
            "knowledge_gap": gap,
            "research_plan": plan,
            "hypotheses": hypotheses,
            "routing": {
                "current_stratum": "unknown_new_archetype",
                "allowed_next_state": "provisional_archetype",
                "downstream_roles_blocked": True,
            },
        })
        for hypothesis in hypotheses:
            candidate_groups[str(hypothesis["hypothesis_id"])].append({
                "project": project,
                "hypothesis": hypothesis,
            })

    candidates = [
        _build_provisional_candidate(
            hypothesis_id, rows,
            minimum_cases=minimum_cases,
            minimum_confidence=minimum_confidence,
            minimum_lineages=minimum_lineages,
            minimum_digests=minimum_digests,
            minimum_markers=minimum_markers,
        )
        for hypothesis_id, rows in sorted(candidate_groups.items())
    ]
    if candidates:
        status = "provisional_candidates"
    elif intakes:
        status = "research_required"
    else:
        status = "clear"
    return {
        "artifact_type": "UnknownProjectLifecycle",
        "status": status,
        "intake_count": len(intakes),
        "provisional_candidate_count": len(candidates),
        "intakes": intakes,
        "provisional_candidates": candidates,
        "policy": {
            "minimum_confirmed_projects": minimum_cases,
            "minimum_evidence_confidence": minimum_confidence,
            "minimum_independent_lineages": minimum_lineages,
            "minimum_unique_evidence_digests": minimum_digests,
            "minimum_candidate_markers": minimum_markers,
            "unknown_is_quarantined": True,
            "automatic_stratum_creation_forbidden": True,
            "automatic_kb_promotion_forbidden": True,
        },
    }


def build_known_strata_regression_baseline(cells: list[dict[str, Any]]) -> dict[str, Any]:
    protected = [
        {"role_id": row["role_id"], "project_stratum": row["project_stratum"], "score": row["score"]}
        for row in cells
        if row.get("project_stratum") != "unknown_new_archetype" and row.get("maturity") == "mature"
    ]
    return {
        "status": "active" if protected else "empty",
        "protected_cell_count": len(protected),
        "protected_cells": protected,
        "policy": {
            "unknown_observations_cannot_change_known_cell_scores": True,
            "regression_reopens_only_affected_role_stratum": True,
        },
    }


def _build_provisional_candidate(
    hypothesis_id: str,
    rows: list[dict[str, Any]],
    *,
    minimum_cases: int,
    minimum_confidence: float,
    minimum_lineages: int,
    minimum_digests: int,
    minimum_markers: int,
) -> dict[str, Any]:
    first = dict(rows[0]["hypothesis"])
    source_cases = []
    for row in rows:
        hypothesis = dict(row["hypothesis"])
        confidence = float(hypothesis.get("confidence") or 0.0)
        digests = [
            dict(value) for value in hypothesis.get("source_digests", [])
            if isinstance(value, dict) and value.get("evidence_hash")
        ]
        asserted_status = str(hypothesis.get("status") or "observed")
        confirmed = (
            asserted_status in {"confirmed", "accepted", "verified"}
            and confidence >= minimum_confidence
            and bool(digests)
        )
        source_cases.append({
            "project": row["project"],
            "status": "confirmed" if confirmed else "observed",
            "confidence": confidence,
            "source_digests": digests,
            "source_lineage": str(hypothesis.get("source_lineage") or ""),
        })
    markers = sorted(set(str(value) for row in rows for value in row["hypothesis"].get("candidate_markers", []) if value))
    confirmed = [row for row in source_cases if row["status"] == "confirmed"]
    lineages = {row["source_lineage"] for row in confirmed if row["source_lineage"]}
    evidence_digests = {
        str(digest["evidence_hash"])
        for row in confirmed
        for digest in row["source_digests"]
    }
    cluster_checks = {
        "minimum_confirmed_projects": len({row["project"] for row in confirmed}) >= minimum_cases,
        "minimum_independent_lineages": len(lineages) >= minimum_lineages,
        "minimum_unique_evidence_digests": len(evidence_digests) >= minimum_digests,
        "minimum_candidate_markers": len(markers) >= minimum_markers,
    }
    cluster_gaps = [name for name, passed in cluster_checks.items() if not passed]
    proposed_record = {
        "record_type": "project_archetype_rule",
        "rule_id": hypothesis_id,
        "archetype": hypothesis_id,
        "label": str(first.get("label") or hypothesis_id),
        "evidence_strength": "provisional",
        "match": {"text_contains_any": markers, "min_score": 1},
        "first_slice": {"name": str(first.get("first_slice_hint") or "researcher_defined_slice")},
        "candidate_origin": {"reason": "unknown project lifecycle", "projects": [row["project"] for row in rows]},
    }
    candidate = build_kb_candidate(
        record_type="project_archetype_rule",
        proposed_record=proposed_record,
        source_cases=source_cases,
        teacher_reference="Researcher source digests",
        min_confirmed_cases=minimum_cases,
    )
    gated_status = str(candidate["status"]) if not cluster_gaps else "collect_more_cases"
    return {
        "artifact_type": "ProvisionalArchetypeCandidate",
        "hypothesis_id": hypothesis_id,
        "status": gated_status,
        "confirmed_project_count": sum(row["status"] == "confirmed" for row in source_cases),
        "observed_project_count": len(source_cases),
        "independent_lineage_count": len(lineages),
        "unique_evidence_digest_count": len(evidence_digests),
        "cluster_checks": cluster_checks,
        "cluster_gaps": cluster_gaps,
        "candidate": candidate,
        "promotion_gate": {
            "status": gated_status,
            "automatic_promotion": False,
            "next_action": _next_action(gated_status),
        },
    }


def _next_action(status: str) -> str:
    return {
        "collect_more_cases": "collect_independent_confirmed_projects",
        "needs_teacher_approval": "request_external_teacher_review",
        "needs_codex_approval": "request_codex_developer_review",
        "ready_for_human_merge": "perform_explicit_human_kb_merge",
    }.get(status, "keep_candidate_quarantined")
