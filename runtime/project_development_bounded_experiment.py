"""Planning-only proposal and admission for a bounded follow-up experiment."""

from __future__ import annotations

from typing import Any

from .project_development_boundary_interpreter import contrast_for_hypothesis


def build_bounded_experiment_proposal(
    *,
    revision: dict[str, Any],
    hypothesis: dict[str, Any],
    policy: dict[str, Any],
) -> dict[str, Any]:
    experiment_policy = _experiment_policy(policy)
    adjustment = dict(dict(revision.get("revised_decision") or {}).get("planning_adjustment") or {})
    target = str(adjustment.get("target") or "")
    evidence_requirements = list(adjustment.get("required_evidence") or [])
    revision_number = revision.get("revision")
    hypothesis_kind = str(hypothesis.get("hypothesis_kind") or "")
    contrast_source = contrast_for_hypothesis(hypothesis_kind)
    active_operator = dict(dict(hypothesis.get("evidence") or {}).get("active_kb_operator") or {})
    proposal_id = f"replan-r{revision_number}:{hypothesis_kind}" if revision_number else ""
    constraints = {
        "planning_only": True,
        "execution_authorized": False,
        "developer_handoff_allowed": False,
        "executor_rerun_allowed": False,
        "source_changes_allowed": False,
        "memory_promotion_allowed": False,
    }
    checks = {
        "bounded_experiment_is_enabled": experiment_policy.get("enabled") is True,
        "revision_is_planning_only": revision.get("status") == "planning_only",
        "target_is_present": bool(target),
        "strategy_is_present": bool(adjustment.get("strategy")),
        "evidence_requirements_are_present": bool(evidence_requirements),
        "source_contrast_is_allowlisted": bool(contrast_source.get("contrast_id")),
        "active_operator_matches_hypothesis": (
            not active_operator
            or active_operator.get("hypothesis_kind") == hypothesis_kind
            and active_operator.get("status") == "validated_active"
        ),
        "execution_is_forbidden": experiment_policy.get("execution_authorized") is False,
    }
    status = "proposed" if all(checks.values()) else "blocked"
    return {
        "artifact_type": "ProjectDevelopmentBoundedExperimentProposal",
        "status": status,
        "proposal_id": proposal_id,
        "revision": revision_number,
        "target": target,
        "contrast_source": contrast_source,
        "hypothesis_kind": hypothesis_kind,
        "active_kb_operator": active_operator or None,
        "strategy": adjustment.get("strategy"),
        "objective": (
            f"Collect bounded planning evidence for {hypothesis_kind} at {target}"
            if target and hypothesis_kind else None
        ),
        "evidence_requirements": evidence_requirements,
        "budget": {
            "maximum_targets": int(experiment_policy.get("maximum_targets") or 0),
            "maximum_source_files": int(experiment_policy.get("maximum_source_files") or 0),
            "maximum_contrast_sources": int(
                experiment_policy.get("maximum_contrast_sources") or 0
            ),
            "maximum_evidence_requirements": int(
                experiment_policy.get("maximum_evidence_requirements") or 0
            ),
            "execution_runs": 0,
            "source_changes": 0,
        },
        "allowed_actions": list(experiment_policy.get("allowed_actions") or []),
        "stop_conditions": list(experiment_policy.get("required_stop_conditions") or []),
        "constraints": constraints,
        "checks": checks,
        "blocking_reasons": [name for name, passed in checks.items() if not passed],
    }


def admit_bounded_experiment_proposal(
    *,
    proposal: dict[str, Any],
    revision: dict[str, Any],
    hypothesis: dict[str, Any],
    policy: dict[str, Any],
) -> dict[str, Any]:
    experiment_policy = _experiment_policy(policy)
    constraints = dict(proposal.get("constraints") or {})
    revision_constraints = dict(revision.get("constraints") or {})
    budget = dict(proposal.get("budget") or {})
    expected_target = str(hypothesis.get("origin_target") or "")
    target = str(proposal.get("target") or "")
    contrast_source = dict(proposal.get("contrast_source") or {})
    active_operator = dict(proposal.get("active_kb_operator") or {})
    hypothesis_operator = dict(dict(hypothesis.get("evidence") or {}).get("active_kb_operator") or {})
    configured_contrast = contrast_for_hypothesis(str(proposal.get("hypothesis_kind") or ""))
    allowed_actions = set(experiment_policy.get("allowed_actions") or [])
    required_stops = set(experiment_policy.get("required_stop_conditions") or [])
    checks = {
        "proposal_is_proposed": proposal.get("status") == "proposed",
        "revision_is_planning_only": revision.get("status") == "planning_only",
        "revision_identity_matches": proposal.get("revision") == revision.get("revision"),
        "target_matches_hypothesis": bool(target) and target == expected_target,
        "target_is_revision_allowlisted": revision_constraints.get("allowed_targets") == [target],
        "single_target_budget": int(budget.get("maximum_targets") or 0) == 1,
        "paired_source_file_budget": int(budget.get("maximum_source_files") or 0) == 2,
        "single_contrast_source_budget": int(budget.get("maximum_contrast_sources") or 0) == 1,
        "contrast_source_is_configured": bool(configured_contrast) and contrast_source == configured_contrast,
        "contrast_source_is_distinct": contrast_source.get("target") != target,
        "active_operator_identity_matches": active_operator == hypothesis_operator,
        "evidence_budget_is_bounded": (
            len(list(proposal.get("evidence_requirements") or []))
            <= int(budget.get("maximum_evidence_requirements") or 0)
            <= int(experiment_policy.get("maximum_evidence_requirements") or 0)
        ),
        "actions_are_allowlisted": (
            bool(proposal.get("allowed_actions"))
            and set(proposal.get("allowed_actions") or []).issubset(allowed_actions)
        ),
        "stop_conditions_are_complete": required_stops.issubset(
            set(proposal.get("stop_conditions") or [])
        ),
        "execution_is_forbidden": (
            experiment_policy.get("execution_authorized") is False
            and constraints.get("execution_authorized") is False
            and int(budget.get("execution_runs") or 0) == 0
        ),
        "developer_handoff_is_forbidden": constraints.get("developer_handoff_allowed") is False,
        "executor_rerun_is_forbidden": constraints.get("executor_rerun_allowed") is False,
        "source_changes_are_forbidden": (
            constraints.get("source_changes_allowed") is False
            and int(budget.get("source_changes") or 0) == 0
        ),
        "memory_promotion_is_forbidden": constraints.get("memory_promotion_allowed") is False,
    }
    admitted = all(checks.values())
    return {
        "artifact_type": "ProjectDevelopmentBoundedExperimentAdmission",
        "status": "admitted_for_planning" if admitted else "blocked",
        "checks": checks,
        "blocking_reasons": [name for name, passed in checks.items() if not passed],
        "proposal_id": proposal.get("proposal_id"),
        "next_role": "researcher" if admitted else "human",
        "execution_authorized": False,
    }


def _experiment_policy(policy: dict[str, Any]) -> dict[str, Any]:
    revision_policy = dict(dict(policy.get("feedback_policy") or {}).get("replan_revision") or {})
    return dict(revision_policy.get("bounded_experiment") or {})
