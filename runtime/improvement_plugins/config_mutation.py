"""Config-mutation improvement plugin."""

from __future__ import annotations

from typing import Any


def run(context: dict[str, Any]) -> dict[str, Any]:
    """Trial and optionally promote one diagnosed config mutation."""
    from runtime.self_improvement_evolution_runner import evolve_diagnosed_foundation_policy

    diagnosis = dict(context.get("diagnosis") or {})
    proposed = dict(diagnosis.get("proposed_knowledge") or {})
    if not isinstance(proposed.get("config_mutation_proposal"), dict):
        return {"status": "not_applicable", "reason": "config_mutation_proposal_missing"}
    regression_projects = list(context.get("regression_projects") or [])
    if context.get("requires_regression_cases") and not regression_projects:
        return {"status": "blocked", "reason": "regression_projects_required"}
    evolution = evolve_diagnosed_foundation_policy(
        root=context["root"],
        project_dir=context["project_dir"],
        failure_packet=dict(context["failure_packet"]),
        diagnosis=diagnosis,
        regression_projects=regression_projects,
        promote=bool(context.get("promote")),
    )
    if evolution is None:
        return {"status": "not_applicable", "reason": "proposal_not_materialized"}
    promoted = bool(dict(evolution.get("promotion") or {}).get("applied"))
    accepted = evolution.get("status") == "passed" and evolution.get("decision") == "accepted"
    return {
        "status": "promoted" if promoted else "trial_passed" if accepted else "blocked",
        "change_type": "config_mutation_proposal",
        "evolution": evolution,
        "promotion_applied": promoted,
    }
