"""Feedback and terminal artifact helpers for project development experiments."""

from __future__ import annotations

from typing import Any


def build_project_development_execution_feedback(
    *,
    handoff: dict[str, Any],
    experiment: dict[str, Any],
    reassessment: dict[str, Any],
    policy: dict[str, Any],
) -> dict[str, Any]:
    feedback_policy = dict(policy.get("feedback_policy") or {})
    patch_reason = str(experiment.get("patch_reason") or "")
    failed_checks = [str(value) for value in reassessment.get("failed_checks") or []]
    admission = dict(experiment.get("admission") or {})
    admission_blockers = set(admission.get("blocking_reasons") or [])
    missing_reducer = (
        experiment.get("status") == "blocked"
        and "implementation_delta_ready" in admission_blockers
        and admission_blockers <= {
            "implementation_delta_ready",
            "recognition_pilot_route_allows_experiment",
        }
        and admission.get("contract_mode") == "failure_repair"
        and not admission.get("allowed_operator_ids")
        and admission.get("implementation_delta_status") == "semantic_synthesis_required"
        and bool(handoff.get("selected_target"))
    )
    if reassessment.get("status") == "validated":
        decision = "completed"
        reason = "experiment_validated"
    elif handoff.get("status") == "needs_replanning":
        decision = "needs_replanning"
        reason = "role_chain_target_not_aligned"
    elif missing_reducer:
        decision = "research"
        reason = "no_verified_failure_reducer"
    elif research_feedback_reason(patch_reason, feedback_policy):
        decision = "research"
        reason = patch_reason
    elif patch_reason in set(feedback_policy.get("controlled_stop_reasons") or []):
        decision = "controlled_stop"
        reason = patch_reason
    elif experiment.get("status") == "failed" and int(experiment.get("patch_count") or 0) > 0:
        decision = "needs_replanning"
        reason = "prepared_patch_verification_failed"
    else:
        decision = "controlled_stop"
        reason = patch_reason or str(reassessment.get("reason") or "experiment_not_actionable")
    next_roles = {
        "research": ["researcher", "architect"],
        "needs_replanning": ["architect"],
        "controlled_stop": ["human"],
        "completed": [],
    }[decision]
    reducer_selection = dict(experiment.get("reducer_selection") or {})
    return {
        "artifact_type": "ProjectDevelopmentExecutionFeedback",
        "status": "not_required" if decision == "completed" else "action_required",
        "decision": decision,
        "reason": reason,
        "next_roles": next_roles,
        "evidence": {
            "experiment_status": experiment.get("status"),
            "selected_target": experiment.get("selected_target") or handoff.get("selected_target"),
            "patch_synthesis_status": experiment.get("patch_synthesis_status"),
            "patch_reason": patch_reason or None,
            "reducer_attempts": list(reducer_selection.get("attempts") or []),
            "failed_checks": failed_checks,
        },
        "constraints": {
            "automatic_retry": bool(feedback_policy.get("automatic_retry", False)),
            "allowed_targets_preserved": bool(feedback_policy.get("preserve_allowed_targets", True)),
            "scope_expansion_allowed": False,
            "source_apply_allowed": False,
        },
    }


def research_feedback_reason(reason: str, policy: dict[str, Any]) -> bool:
    if reason in set(policy.get("research_reasons") or []):
        return True
    return any(reason.endswith(str(suffix)) for suffix in policy.get("research_reason_suffixes") or [])


def not_requested_artifacts() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    return (
        {"artifact_type": "ProjectDevelopmentExperiment", "status": "not_requested", "apply_source": False},
        {"artifact_type": "ProjectDevelopmentReassessment", "status": "not_requested"},
        {"artifact_type": "ProjectDevelopmentValidatedMemory", "status": "not_promoted", "authority": "none"},
    )


def blocked_artifacts(admission: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    return (
        {"artifact_type": "ProjectDevelopmentExperiment", "status": "blocked", "admission": admission, "apply_source": False},
        {"artifact_type": "ProjectDevelopmentReassessment", "status": "not_validated", "reason": "experiment_admission_blocked"},
        {"artifact_type": "ProjectDevelopmentValidatedMemory", "status": "not_promoted", "authority": "none"},
    )
