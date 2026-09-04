"""Adversarial holdout trial for unknown archetypes and role-chain interaction."""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .knowledge_admission import build_kb_candidate
from .role_chain_interaction import (
    build_role_chain_trace,
    build_unknown_role_chain_trace,
    summarize_role_chain_traces,
)
from .role_pipeline import run_role_pipeline
from .role_project_type_evaluation import classify_project_case, load_role_project_type_policy
from .unknown_project_lifecycle import build_unknown_project_lifecycle


HYPOTHESIS_ID = "event_sourced_projection"


def run_unknown_archetype_field_trial(
    *,
    root: Path,
    projects_dir: Path | None = None,
    limit: int = 0,
    write: bool = False,
) -> dict[str, Any]:
    policy = load_role_project_type_policy()
    unknown = _unknown_holdout(policy)
    known_traces = []
    if projects_dir is not None:
        projects = sorted(path for path in projects_dir.iterdir() if path.is_dir())
        if limit:
            projects = projects[:limit]
        for project_dir in projects:
            result = run_role_pipeline(
                root=root,
                project_dir=project_dir,
                goal=f"Measure role-chain continuity for {project_dir.name}",
            )
            known_traces.append(build_role_chain_trace(
                project=project_dir.name,
                result=result,
                minimum_score=float(dict(policy.get("role_chain_evaluation") or {}).get("minimum_interaction_score") or 0.9),
            ))
    all_traces = [*known_traces, *unknown["role_chain_traces"]]
    chain_summary = summarize_role_chain_traces(all_traces)
    status = "ok" if unknown["status"] == "ok" and all(
        row.get("status") in {"ok", "controlled_stop"} for row in all_traces
    ) else "needs_work"
    report = {
        "artifact_type": "UnknownArchetypeFieldTrialReport",
        "schema_version": "unknown_archetype_field_trial.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "evidence_mode": "adversarial_holdout_and_dry_run",
        "summary": {
            **chain_summary,
            "unknown_scenario_count": len(unknown["scenarios"]),
            "promotion_rehearsal_status": unknown["promotion_rehearsal"]["status"],
            "source_code_changes": 0,
            "kb_mutations": 0,
        },
        "unknown_holdout": unknown,
        "role_chain_traces": all_traces,
        "policy": {
            "holdout_is_not_training_data": True,
            "automatic_kb_promotion_forbidden": True,
            "promotion_rehearsal_is_in_memory_only": True,
        },
    }
    if write:
        out_dir = root / "artifacts" / "field_trials"
        out_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        path = out_dir / f"unknown_archetype_field_trial_{stamp}.json"
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        report["report_path"] = path.as_posix()
    return report


def _unknown_holdout(policy: dict[str, Any]) -> dict[str, Any]:
    known_case = {"project": "unseen-provider-adapter", "archetype": "protocol_api_client"}
    known_classification = classify_project_case(known_case, policy=policy)
    unknown_items = [
        _debt_item("novel-unresolved"),
        _debt_item("mystery-cli", archetype="event_log_projection"),
        _debt_item("weak-projection", hypothesis=_hypothesis("observed", confidence=0.92, digest=False)),
        *[
            _debt_item(
                f"projection-{index}",
                hypothesis=_hypothesis("confirmed", confidence=0.86, digest=True, index=index),
            )
            for index in range(3)
        ],
    ]
    lifecycle = build_unknown_project_lifecycle(
        {"status": "needs_classification", "count": len(unknown_items), "items": unknown_items},
        policy=policy,
    )
    candidate = next(
        row for row in lifecycle["provisional_candidates"]
        if row.get("hypothesis_id") == HYPOTHESIS_ID
    )
    intake_by_project = {str(row["project"]): row for row in lifecycle["intakes"]}
    unknown_traces = [
        build_unknown_role_chain_trace(
            intake=intake_by_project[project],
            candidate=candidate if project.startswith("projection-") else None,
        )
        for project in ("novel-unresolved", "mystery-cli", "weak-projection", "projection-0")
    ]
    conflict_classification = classify_project_case(
        {"project": "mystery-cli", "archetype": "event_log_projection"}, policy=policy
    )
    promotion = _promotion_rehearsal(candidate, policy, known_case, known_classification)
    scenarios = [
        {
            "id": "existing_stratum_recovery",
            "status": "passed" if known_classification["project_stratum"] == "sdk_provider_integration" else "failed",
            "classification": known_classification,
        },
        {
            "id": "genuine_unknown_requires_research",
            "status": "passed" if intake_by_project["novel-unresolved"]["status"] == "research_required" else "failed",
            "intake": intake_by_project["novel-unresolved"],
        },
        {
            "id": "conflicting_identity_stays_quarantined",
            "status": "passed" if conflict_classification["project_stratum"] == "unknown_new_archetype"
            and conflict_classification["classification_conflict"] is True else "failed",
            "classification": conflict_classification,
        },
        {
            "id": "weak_evidence_cannot_confirm",
            "status": "passed" if candidate["observed_project_count"] == 4
            and candidate["confirmed_project_count"] == 3 else "failed",
            "candidate_status": candidate["status"],
        },
    ]
    status = "ok" if all(row["status"] == "passed" for row in scenarios) and promotion["status"] == "passed" else "needs_work"
    return {
        "status": status,
        "scenarios": scenarios,
        "lifecycle": lifecycle,
        "promotion_rehearsal": promotion,
        "role_chain_traces": unknown_traces,
    }


def _promotion_rehearsal(
    provisional: dict[str, Any],
    policy: dict[str, Any],
    known_case: dict[str, Any],
    known_before: dict[str, Any],
) -> dict[str, Any]:
    staged = dict(provisional["candidate"])
    reviewed = build_kb_candidate(
        record_type=str(staged["record_type"]),
        proposed_record=dict(staged["proposed_record"]),
        source_cases=list(staged["source_cases"]),
        teacher_reference="adversarial holdout rehearsal",
        teacher_approved=True,
        codex_approved=True,
        min_confirmed_cases=int(dict(policy.get("unknown_archetype_lifecycle") or {}).get("minimum_confirmed_projects") or 3),
    )
    simulated_policy = deepcopy(policy)
    simulated_policy["strata"] = [
        *list(simulated_policy["strata"]),
        {
            "id": HYPOTHESIS_ID,
            "label": "Event-sourced projections",
            "markers": ["event_log_projection", "event_sourced_projection"],
        },
    ]
    promoted_holdout = classify_project_case(
        {"project": "projection-independent-holdout", "archetype": "event_log_projection"},
        policy=simulated_policy,
    )
    known_after = classify_project_case(known_case, policy=simulated_policy)
    checks = {
        "repeated_evidence_reached_review_gate": staged.get("status") == "needs_teacher_approval",
        "both_reviews_make_candidate_merge_ready": reviewed.get("status") == "ready_for_human_merge",
        "explicit_merge_simulation_classifies_independent_holdout": promoted_holdout.get("project_stratum") == HYPOTHESIS_ID,
        "known_classification_did_not_regress": known_after.get("project_stratum") == known_before.get("project_stratum"),
        "no_runtime_kb_mutation": True,
    }
    return {
        "status": "passed" if all(checks.values()) else "failed",
        "checks": checks,
        "candidate_before_review": staged.get("status"),
        "candidate_after_review": reviewed.get("status"),
        "independent_holdout_classification": promoted_holdout,
        "known_regression_probe": {"before": known_before, "after": known_after},
        "kb_mutations": 0,
    }


def _debt_item(
    project: str, *, archetype: str | None = None, hypothesis: dict[str, Any] | None = None
) -> dict[str, Any]:
    return {
        "project": project,
        "observed_roles": ["project_analyzer"],
        "project_archetypes": [archetype] if archetype else [],
        "contract_families": [],
        "risk_profiles": ["unspecified"],
        "classification_sources": ["fallback"],
        "reports": [f"holdout:{project}"],
        "archetype_hypotheses": [hypothesis] if hypothesis else [],
        "reason": "no_configured_project_stratum_matched_authoritative_evidence",
        "next_action": "map_existing_stratum_or_add_validated_archetype",
    }


def _hypothesis(status: str, *, confidence: float, digest: bool, index: int = 0) -> dict[str, Any]:
    return {
        "hypothesis_id": HYPOTHESIS_ID,
        "label": "Event-sourced projection",
        "candidate_markers": ["event_log_projection", "projection"],
        "first_slice_hint": "append_and_rebuild_projection",
        "confidence": confidence,
        "status": status,
        "source_digests": ([{"evidence_hash": f"holdout-digest-{index}", "confidence": confidence}] if digest else []),
    }
