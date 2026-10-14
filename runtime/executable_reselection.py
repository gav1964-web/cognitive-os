"""Build Architect feedback from failed executable acceptance evidence."""

from __future__ import annotations

import copy
from typing import Any

from .technical_spec_policy import load_technical_spec_policy


def build_execution_reselection_request(
    executor: dict[str, Any], technical_spec: dict[str, Any]
) -> dict[str, Any]:
    policy = dict(load_technical_spec_policy().get("first_slice_reselection") or {})
    if not policy.get("execution_feedback_enabled", False):
        return {"status": "not_required", "reason": "execution_feedback_disabled"}
    summary = _acceptance_summary(executor)
    acceptance_status = _acceptance_status(executor)
    target = str(dict(technical_spec.get("extraction_contract") or {}).get("candidate") or "")
    callable_count = int(summary.get("callable_harness_count") or 0)
    signal = str(summary.get("signal_strength") or "")
    skipped = [dict(row) for row in summary.get("skipped_targets") or [] if isinstance(row, dict)]
    allowed = {str(reason) for reason in policy.get("execution_rejection_reasons") or []}
    actionable = [row for row in skipped if str(row.get("reason") or "") in allowed]
    if acceptance_status == "failed" and target and "executable_acceptance_failed" in allowed:
        actionable.append({
            "target": target,
            "reason": "executable_acceptance_failed",
            "detail": "callable harness executed but executable acceptance failed",
            "recovery": "reject the failed target and select a lower-cost executable contract",
        })
    callable_passed = (
        acceptance_status == "passed"
        and callable_count > 0
        and signal == "executable_callable"
    )
    if not target or callable_passed or not actionable:
        return {
            "artifact_type": "ExecutableReselectionRequest",
            "status": "not_required",
            "current_target": target or None,
        }
    return {
        "artifact_type": "ExecutableReselectionRequest",
        "status": "required",
        "trigger": "executable_acceptance_rejected",
        "current_target": target,
        "blocking_evidence": {
            "acceptance_signal": signal or "meta_only",
            "callable_harness_count": callable_count,
            "skipped_targets": actionable,
            "skipped_reason_counts": dict(summary.get("skipped_reason_counts") or {}),
        },
        "authority": "architect_reselection_required_after_executor_evidence",
        "forbidden_actions": [
            "retry_same_target_without_new_contract_evidence",
            "promote_meta_only_acceptance",
            "expand_writable_scope_without_architect_decision",
        ],
        "next_step": "return_to_architect_and_rebuild_spec_plan_test",
    }


def record_rejected_target(
    architecture_decision: dict[str, Any],
    request: dict[str, Any],
    *,
    iteration: int,
) -> dict[str, Any]:
    revised = copy.deepcopy(architecture_decision)
    target = str(request.get("current_target") or "")
    outcome = {
        "artifact_type": "ExecutableReselectionOutcome",
        "iteration": iteration,
        "status": "rejected_by_executable_acceptance",
        "trigger": request.get("trigger"),
        "selected_targets": [target] if target else [],
        "blocking_evidence": copy.deepcopy(request.get("blocking_evidence") or {}),
        "authority": "executor_evidence_returned_to_architect",
    }
    history = list(revised.get("first_slice_reselection_history") or [])
    history.append(outcome)
    revised["first_slice_reselection_history"] = history
    return revised


def feedback_iteration_limit() -> int:
    policy = dict(load_technical_spec_policy().get("first_slice_reselection") or {})
    return max(0, int(policy.get("execution_feedback_max_iterations") or 0))


def feedback_resource_failure_limit() -> int:
    policy = dict(load_technical_spec_policy().get("first_slice_reselection") or {})
    return max(1, int(policy.get("execution_feedback_max_resource_failures") or 1))


def _acceptance_summary(executor: dict[str, Any]) -> dict[str, Any]:
    test_result = dict(executor.get("test_result") or {})
    acceptance = dict(test_result.get("executable_acceptance_result") or {})
    return dict(acceptance.get("summary") or {})


def _acceptance_status(executor: dict[str, Any]) -> str:
    test_result = dict(executor.get("test_result") or {})
    acceptance = dict(test_result.get("executable_acceptance_result") or {})
    return str(acceptance.get("status") or "")
