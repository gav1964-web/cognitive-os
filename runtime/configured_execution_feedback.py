"""Close configured role chains with bounded executable target feedback."""

from __future__ import annotations

from typing import Any, Callable

from .architect_first_slice_reselection import (
    _revised_architecture_decision,
    reselect_architecture_first_slice,
)
from .configured_role_pipeline import artifact_by_type
from .executable_reselection import (
    build_execution_reselection_request,
    feedback_iteration_limit,
    record_rejected_target,
)
from .evaluation_target_clamp import clamp_architecture_target

Artifacts = dict[str, dict[str, Any]]
Rerun = Callable[[dict[str, Any]], tuple[Artifacts, dict[str, Any]]]


def close_configured_execution_feedback(
    *,
    artifacts: Artifacts,
    executor: dict[str, Any],
    project_report: dict[str, Any],
    rerun: Rerun,
) -> tuple[Artifacts, dict[str, Any], dict[str, Any]]:
    """Return the best chain after Architect-owned executable reselection."""
    current_artifacts = artifacts
    current_executor = executor
    history: list[dict[str, Any]] = []
    status = "not_required"
    for iteration in range(1, feedback_iteration_limit() + 1):
        spec = artifact_by_type(current_artifacts, "TechnicalSpec")
        adr = artifact_by_type(current_artifacts, "ArchitectureDecisionRecord")
        request = build_execution_reselection_request(
            _executor_envelope(current_executor), spec
        )
        if request.get("status") != "required":
            status = "resolved" if history else "not_required"
            break
        rejected = record_rejected_target(adr, request, iteration=iteration)
        resolution = reselect_architecture_first_slice(
            architecture_decision=rejected,
            technical_spec={**spec, "first_slice_reselection_request": request},
            project_report=project_report,
            iteration=iteration,
        )
        outcome = dict(resolution.get("outcome") or {})
        targets = list(outcome.get("selected_targets") or [])
        history.append({
            "iteration": iteration,
            "rejected_target": request.get("current_target"),
            "blocking_evidence": request.get("blocking_evidence"),
            "resolution_status": resolution.get("status"),
            "selected_targets": targets[:1],
            "candidate_window": targets,
            "selection_policy_ids": list(
                dict(resolution.get("outcome") or {}).get("selection_policy_ids") or []
            ),
        })
        if resolution.get("status") != "selected" or not targets:
            status = str(resolution.get("status") or "exhausted")
            break
        expanded = dict(dict(resolution.get("architecture_decision") or {}).get("source_context") or {})
        narrowed_outcome = {**outcome, "selected_targets": targets[:1]}
        revised = _revised_architecture_decision(
            rejected,
            project_report=project_report,
            expanded_context=expanded,
            selected_targets=targets[:1],
            outcome=narrowed_outcome,
        )
        revised = clamp_architecture_target(revised, str(targets[0]))
        current_artifacts, current_executor = rerun(revised)
        rerun_spec = artifact_by_type(current_artifacts, "TechnicalSpec")
        rerun_request = build_execution_reselection_request(
            _executor_envelope(current_executor), rerun_spec
        )
        if rerun_request.get("status") != "required":
            status = "resolved"
            break
    else:
        status = "iteration_limit"
    feedback = {
        "status": status,
        "iteration_count": len(history),
        "history": history,
    }
    for artifact in current_artifacts.values():
        if isinstance(artifact, dict):
            artifact["execution_reselection_status"] = status
            artifact["execution_reselection_history"] = history
    return current_artifacts, current_executor, feedback


def _executor_envelope(executor: dict[str, Any]) -> dict[str, Any]:
    summary = {
        "signal_strength": executor.get("acceptance_signal"),
        "callable_harness_count": executor.get("callable_harness_count"),
        "skipped_reason_counts": dict(executor.get("acceptance_skipped_reasons") or {}),
        "skipped_targets": list(executor.get("acceptance_skipped_targets") or []),
    }
    return {
        "test_result": {
            "executable_acceptance_result": {
                "status": executor.get("executable_acceptance"),
                "summary": summary,
            }
        }
    }
