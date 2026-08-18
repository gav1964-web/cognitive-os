"""Acceptance coverage gates for single and composite Programmer patches."""

from __future__ import annotations

from typing import Any, Callable


def repair_needed(
    test_result: dict[str, Any],
    candidate_attempt: dict[str, Any],
    implementation_plan: dict[str, Any] | None,
    *,
    llm_enabled: Callable[[], bool],
) -> bool:
    if not llm_enabled():
        return False
    if candidate_attempt.get("status") == "blocked":
        return candidate_attempt.get("reason") in {
            "blocked_invalid_candidate",
            "diff_apply_failed",
            "diff_noop",
        }
    if candidate_attempt.get("status") != "applied_in_sandbox":
        return False
    if test_result.get("status") == "failed":
        return True
    summary = dict(dict(test_result.get("executable_acceptance_result") or {}).get("summary") or {})
    return not acceptance_covers_plan(summary, implementation_plan)


def enforce_prepared_patch_acceptance(
    test_result: dict[str, Any], synthesis: dict[str, Any], implementation_plan: dict[str, Any]
) -> None:
    summary = dict(dict(test_result.get("executable_acceptance_result") or {}).get("summary") or {})
    if synthesis.get("status") != "prepared" or acceptance_covers_plan(summary, implementation_plan):
        return
    test_result["status"] = "failed"
    test_result["summary"]["failed"] = int(test_result["summary"].get("failed") or 0) + 1
    gate_status = (
        "failed_incomplete_callable_coverage"
        if summary.get("signal_strength") == "executable_callable"
        else "failed_non_callable_acceptance"
    )
    test_result["summary"]["prepared_patch_acceptance_gate"] = gate_status


def acceptance_covers_plan(summary: dict[str, Any], plan: dict[str, Any] | None) -> bool:
    if summary.get("signal_strength") != "executable_callable":
        return False
    expected = _planned_targets(plan or {})
    if not expected:
        return True
    callable_targets = {str(item) for item in list(summary.get("callable_targets") or []) if item}
    return expected.issubset(callable_targets)


def _planned_targets(plan: dict[str, Any]) -> set[str]:
    intent = dict(plan.get("patch_intent") or {})
    primary = str(intent.get("target_symbol") or dict(plan.get("implementation_target") or {}).get("candidate") or "")
    targets = [primary]
    targets.extend(
        str(item.get("target") or "")
        for item in list(plan.get("change_plan") or plan.get("implementation_steps") or [])
        if isinstance(item, dict)
    )
    return {target for target in targets if target}
