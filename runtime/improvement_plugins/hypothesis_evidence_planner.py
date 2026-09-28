"""Plan bounded evidence acquisition before an improvement plugin is implemented."""

from __future__ import annotations

from typing import Any

from runtime.self_improvement_hypothesis_compiler import load_hypothesis_compiler_config


def run(context: dict[str, Any]) -> dict[str, Any]:
    hypothesis = dict(context.get("compiled_hypothesis") or {})
    if hypothesis.get("candidate_type") != "evidence_collection_plan":
        return {"status": "not_applicable", "reason": "evidence_plan_hypothesis_required"}
    reports = _latest_by_project([dict(row) for row in context.get("evidence_reports") or []])
    counterexamples = _latest_by_project([
        dict(row) for row in context.get("counterexample_reports") or []
    ])
    metrics = _metrics(reports)
    policy = dict(load_hypothesis_compiler_config().get("evidence_planner") or {})
    minimum = int(policy.get("minimum_consistent_action_cases") or 2)
    action, reason = _next_action(
        metrics, minimum,
        resolve_negative=bool(policy.get("negative_transfer_requires_resolution", True)),
    )
    maximum = max(1, int(policy.get("maximum_plan_projects") or 12))
    plan = {
        "artifact_type": "HypothesisEvidenceCollectionPlan",
        "hypothesis_id": hypothesis.get("hypothesis_id"),
        "status": "planned",
        "next_action": action,
        "reason": reason,
        "failure_class": hypothesis.get("failure_class"),
        "portable_signature": hypothesis.get("portable_signature"),
        "observed_metrics": metrics,
        "positive_projects": metrics["positive_projects"][:maximum],
        "negative_projects": metrics["negative_projects"][:maximum],
        "unresolved_projects": metrics["unresolved_projects"][:maximum],
        "counterexample_projects": [
            str(row.get("project")) for row in counterexamples[:maximum] if row.get("project")
        ],
        "completion_gate": {
            "minimum_consistent_positive_actions": minimum,
            "negative_transfer_count": 0,
            "independent_project_required": True,
            "same_evaluator_required": True,
            "source_project_unchanged": True,
        },
        "authority": "evidence_plan_only",
        "forbidden": [
            "runtime_plugin_generation", "kb_promotion", "threshold_change",
            "source_project_mutation",
        ],
    }
    return {
        "status": "evidence_planned", "change_type": "compiled_hypothesis_evidence_gap",
        "promotion_applied": False, "plan": plan,
    }


def _metrics(reports: list[dict[str, Any]]) -> dict[str, Any]:
    positive, negative, unresolved = [], [], []
    plugin_confirmed = set()
    selected_missing = []
    for report in reports:
        project = str(report.get("project") or "")
        outcome = dict(report.get("outcome") or {})
        delta = float(outcome.get("score_delta") or 0.0)
        baseline = dict(report.get("baseline") or {})
        trained = dict(report.get("trained_attempt") or {})
        changed = bool(
            baseline.get("selected_extraction_candidate")
            and trained.get("selected_extraction_candidate")
            and baseline.get("selected_extraction_candidate") != trained.get("selected_extraction_candidate")
        )
        if delta > 0 and changed and not outcome.get("role_regressions"):
            positive.append(project)
        elif delta < 0 or outcome.get("role_regressions"):
            negative.append(project)
        else:
            unresolved.append(project)
        if not baseline.get("selected_extraction_candidate"):
            selected_missing.append(project)
        for cycle_name in ("improvement_plugin_cycle", "post_training_admission"):
            for attempt in list(dict(report.get(cycle_name) or {}).get("attempts") or []):
                row = dict(attempt or {})
                if row.get("status") in {"trial_passed", "promoted"}:
                    plugin_confirmed.add(project)
    return {
        "project_count": len({str(row.get("project") or "") for row in reports if row.get("project")}),
        "positive_action_count": len(set(positive)),
        "negative_transfer_count": len(set(negative)),
        "unresolved_count": len(set(unresolved)),
        "selected_candidate_missing_count": len(set(selected_missing)),
        "plugin_confirmed_project_count": len(plugin_confirmed),
        "positive_projects": sorted(set(positive)),
        "negative_projects": sorted(set(negative)),
        "unresolved_projects": sorted(set(unresolved)),
    }


def _next_action(
    metrics: dict[str, Any], minimum: int, *, resolve_negative: bool,
) -> tuple[str, str]:
    if resolve_negative and int(metrics["negative_transfer_count"]):
        return "resolve_cluster_contradiction", "negative transfer forbids plugin compilation"
    if int(metrics["selected_candidate_missing_count"]):
        return "discover_bounded_executable_candidates", "baseline target evidence is missing"
    if int(metrics["plugin_confirmed_project_count"]):
        return "confirm_existing_plugin_effect", "one plugin effect needs independent reproduction"
    if int(metrics["positive_action_count"]) < minimum:
        return "collect_independent_measured_actions", "consistent action evidence is below threshold"
    return "recompile_hypothesis", "action evidence threshold is satisfied"


def _latest_by_project(reports: list[dict[str, Any]]) -> list[dict[str, Any]]:
    projects: dict[str, dict[str, Any]] = {}
    for report in reports:
        project = str(report.get("project") or "")
        if project:
            projects.setdefault(project, report)
    return [projects[key] for key in sorted(projects)]
