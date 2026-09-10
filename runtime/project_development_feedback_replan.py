"""Replan/research helpers for project-development feedback continuation."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from .project_development_boundary_interpreter import interpret_boundary
from .project_development_source_evidence import collect_python_target_facts


def _build_replan_revision(
    *,
    feedback: dict[str, Any],
    hypothesis: dict[str, Any],
    architect_decision: dict[str, Any],
    baseline_decision: dict[str, Any] | None,
    baseline_outcome_contract: dict[str, Any] | None,
    policy: dict[str, Any],
) -> dict[str, Any]:
    revision_policy = dict(dict(policy.get("feedback_policy") or {}).get("replan_revision") or {})
    original_decision = deepcopy(baseline_decision or {})
    original_outcome = deepcopy(baseline_outcome_contract or {})
    target = str(hypothesis.get("origin_target") or "")
    allowed_targets = list(architect_decision.get("allowed_targets") or [])
    selected_issue = dict(original_decision.get("selected_issue") or {})
    baseline_targets = {
        str(value)
        for value in [
            *list(selected_issue.get("affected_targets") or []),
            *list(selected_issue.get("evidence") or []),
            *list(dict(original_decision.get("selected_option") or {}).get("evidence") or []),
        ]
        if value
    }
    required_checks = list(original_outcome.get("required_checks") or [])
    expected_checks = list(dict(policy.get("outcome_policy") or {}).get("required_checks") or [])
    increment = int(revision_policy.get("maximum_revision_increment") or 0)
    checks = {
        "baseline_decision_is_valid": (
            original_decision.get("artifact_type") == "ProjectDevelopmentDecision"
            and original_decision.get("status") == "selected"
            and bool(original_decision.get("selected_option"))
        ),
        "baseline_outcome_contract_is_valid": (
            original_outcome.get("artifact_type") == "ProjectDevelopmentOutcomeContract"
            and original_outcome.get("status") == "defined"
        ),
        "architect_authorized_replan": architect_decision.get("decision") == "replan",
        "target_scope_is_preserved": (
            revision_policy.get("preserve_allowed_targets") is True
            and bool(target)
            and allowed_targets == [target]
            and target in baseline_targets
        ),
        "required_checks_are_preserved": (
            revision_policy.get("preserve_required_checks") is True
            and required_checks == expected_checks
        ),
        "revision_increment_is_bounded": increment == 1,
        "planning_only_is_required": revision_policy.get("planning_only") is True,
        "developer_handoff_is_forbidden": revision_policy.get("developer_handoff_allowed") is False,
        "executor_rerun_is_forbidden": revision_policy.get("executor_rerun_allowed") is False,
        "source_changes_are_forbidden": revision_policy.get("source_changes_allowed") is False,
    }
    constraints = {
        "allowed_targets": [target] if target else [],
        "planning_only": True,
        "developer_handoff_allowed": False,
        "executor_rerun_allowed": False,
        "source_changes_allowed": False,
    }
    if not all(checks.values()):
        return {
            "artifact_type": "ProjectDevelopmentReplanRevision",
            "status": "blocked",
            "revision": None,
            "authority": "architect_feedback",
            "origin": _revision_origin(feedback, hypothesis, architect_decision),
            "checks": checks,
            "failed_checks": [name for name, passed in checks.items() if not passed],
            "revised_decision": None,
            "revised_outcome_contract": None,
            "constraints": constraints,
        }
    decision_revision = int(original_decision.get("revision") or 1) + increment
    outcome_revision = int(original_outcome.get("revision") or 1) + increment
    revised_decision = deepcopy(original_decision)
    revised_decision.update({
        "status": "replanned",
        "revision": decision_revision,
        "supersedes_revision": decision_revision - increment,
        "authority": "architect_feedback",
        "planning_adjustment": {
            "hypothesis_kind": hypothesis.get("hypothesis_kind"),
            "strategy": dict(hypothesis.get("proposed_next_experiment") or {}).get("strategy"),
            "target": target,
            "required_evidence": list(
                dict(hypothesis.get("proposed_next_experiment") or {}).get("required_evidence") or []
            ),
        },
        "execution_authorized": False,
    })
    revised_outcome = deepcopy(original_outcome)
    revised_outcome.update({
        "status": "revised_planning_only",
        "revision": outcome_revision,
        "supersedes_revision": outcome_revision - increment,
        "expected_outcome": (
            f"Characterize {hypothesis.get('hypothesis_kind')} for {target} "
            "without widening the approved scope"
        ),
        "required_checks": required_checks,
        "reassessment": dict(hypothesis.get("proposed_next_experiment") or {}).get("strategy"),
        "execution_authorized": False,
    })
    return {
        "artifact_type": "ProjectDevelopmentReplanRevision",
        "status": "planning_only",
        "revision": max(decision_revision, outcome_revision),
        "authority": "architect_feedback",
        "origin": _revision_origin(feedback, hypothesis, architect_decision),
        "checks": checks,
        "failed_checks": [],
        "revised_decision": revised_decision,
        "revised_outcome_contract": revised_outcome,
        "constraints": constraints,
    }


def _revision_origin(
    feedback: dict[str, Any],
    hypothesis: dict[str, Any],
    architect_decision: dict[str, Any],
) -> dict[str, Any]:
    return {
        "feedback_reason": feedback.get("reason"),
        "hypothesis_kind": hypothesis.get("hypothesis_kind"),
        "architect_decision": architect_decision.get("decision"),
        "origin_target": hypothesis.get("origin_target"),
    }


def _build_research_hypothesis(
    project_dir: Path,
    feedback: dict[str, Any],
) -> dict[str, Any]:
    evidence = dict(feedback.get("evidence") or {})
    target = str(evidence.get("selected_target") or "")
    facts = collect_python_target_facts(project_dir, target)
    reason = str(feedback.get("reason") or "")
    attempts = [dict(row) for row in evidence.get("reducer_attempts") or [] if isinstance(row, dict)]
    profile = interpret_boundary({
        "feedback": {"reason": reason},
        "source_facts": facts,
        "reducer_attempts": attempts,
    })
    hypothesis_profile = dict(profile.get("hypothesis") or {})
    active_operator = dict(profile.get("active_kb_operator") or {})
    status = str(hypothesis_profile.get("status") or "knowledge_gap")
    kind = str(profile.get("hypothesis_kind") or profile.get("id") or "unsupported_reducer_shape")
    confidence = float(hypothesis_profile.get("confidence") or 0.0)
    strategy = str(hypothesis_profile.get("strategy") or "resolve_source_and_reducer_evidence")
    return {
        "artifact_type": "ProjectDevelopmentResearchHypothesis",
        "status": status,
        "origin_target": target,
        "hypothesis_kind": kind,
        "confidence": confidence,
        "evidence": {
            "feedback_reason": reason,
            "source_facts": facts,
            "reducer_attempts": attempts,
            "knowledge_profile": profile.get("id"),
            "knowledge_status": profile.get("status"),
            "active_kb_operator": active_operator or None,
        },
        "proposed_next_experiment": {
            "kind": hypothesis_profile.get("experiment_kind"),
            "strategy": strategy,
            "target": target,
            "required_evidence": list(profile.get("required_evidence") or []),
        },
        "constraints": {
            "allowed_targets": [target] if target else [],
            "source_changes_allowed": False,
            "executor_rerun_allowed": False,
            "developer_handoff_allowed": False,
        },
    }


def _build_architect_decision(
    feedback: dict[str, Any],
    hypothesis: dict[str, Any],
    policy: dict[str, Any],
) -> dict[str, Any]:
    feedback_policy = dict(policy.get("feedback_policy") or {})
    target = str(dict(feedback.get("evidence") or {}).get("selected_target") or "")
    hypothesis_target = str(hypothesis.get("origin_target") or "")
    facts = dict(dict(hypothesis.get("evidence") or {}).get("source_facts") or {})
    checks = {
        "feedback_requests_research": feedback.get("decision") == "research",
        "origin_is_source_backed": facts.get("source_backed") is True,
        "target_scope_is_preserved": bool(target) and hypothesis_target == target,
        "hypothesis_kind_is_allowed": hypothesis.get("hypothesis_kind")
        in set(feedback_policy.get("allowed_hypothesis_kinds") or []),
        "confidence_is_sufficient": float(hypothesis.get("confidence") or 0.0)
        >= float(feedback_policy.get("minimum_replan_confidence") or 1.0),
        "automatic_retry_is_disabled": feedback_policy.get("automatic_retry") is False,
        "executor_rerun_is_forbidden": dict(hypothesis.get("constraints") or {}).get(
            "executor_rerun_allowed"
        ) is False,
    }
    if hypothesis.get("status") == "proposed" and all(checks.values()):
        decision = "replan"
        next_role = "project_development"
    elif (
        hypothesis.get("status") in {"research_more", "knowledge_gap"}
        and checks["target_scope_is_preserved"]
        and checks["automatic_retry_is_disabled"]
    ):
        decision = "research_more"
        next_role = "researcher"
    else:
        decision = "controlled_stop"
        next_role = "human"
    return {
        "artifact_type": "ProjectDevelopmentArchitectFeedbackDecision",
        "status": "decided",
        "decision": decision,
        "authority": "architect",
        "checks": checks,
        "failed_checks": [name for name, passed in checks.items() if not passed],
        "allowed_targets": [target] if target else [],
        "next_role": next_role,
        "executor_rerun_allowed": False,
    }
