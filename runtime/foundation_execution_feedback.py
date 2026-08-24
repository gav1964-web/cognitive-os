"""Close foundation-role selection with bounded executable feedback."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from .architect_first_slice_reselection import reselect_architecture_first_slice
from .executable_reselection import (
    build_execution_reselection_request,
    feedback_iteration_limit,
    record_rejected_target,
)
from .foundation_executable_evidence import collect_foundation_executable_evidence


FoundationRerun = Callable[[str], dict[str, Any]]


def run_foundation_execution_feedback(
    *,
    root: Path,
    project_dir: Path,
    initial_result: dict[str, Any],
    rerun: FoundationRerun,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Retry Architect-selected targets after executable acceptance rejects one."""
    current = initial_result
    evidence = _collect(root, project_dir, current)
    best_result, best_evidence = current, evidence
    history: list[dict[str, Any]] = []
    architecture = _artifact(current, "architecture_decision")
    project_report = dict(_artifact(current, "project_map_report").get("content") or {})
    for iteration in range(1, feedback_iteration_limit() + 1):
        spec = _artifact(current, "technical_spec")
        request = build_execution_reselection_request(_executor(evidence), spec)
        if request.get("status") != "required" or not architecture or not project_report:
            break
        rejected = record_rejected_target(architecture, request, iteration=iteration)
        spec_with_request = {**spec, "first_slice_reselection_request": request}
        resolution = reselect_architecture_first_slice(
            architecture_decision=rejected,
            technical_spec=spec_with_request,
            project_report=project_report,
            iteration=iteration,
        )
        targets = list(dict(resolution.get("outcome") or {}).get("selected_targets") or [])
        history.append({
            "iteration": iteration,
            "rejected_target": request.get("current_target"),
            "blocking_evidence": request.get("blocking_evidence"),
            "resolution_status": resolution.get("status"),
            "selected_targets": targets,
        })
        if resolution.get("status") != "selected" or not targets:
            architecture = dict(resolution.get("architecture_decision") or rejected)
            break
        architecture = dict(resolution.get("architecture_decision") or rejected)
        current = rerun(str(targets[0]))
        if current.get("status") != "ok":
            break
        evidence = _collect(root, project_dir, current)
        if _evidence_rank(evidence) > _evidence_rank(best_evidence):
            best_result, best_evidence = current, evidence
    if _evidence_rank(best_evidence) > _evidence_rank(evidence):
        current, evidence = best_result, best_evidence
    if history:
        _attach_feedback(current, evidence, history)
    return current, evidence


def _collect(root: Path, project_dir: Path, result: dict[str, Any]) -> dict[str, Any]:
    spec = _artifact(result, "technical_spec")
    if not spec:
        return {"status": "skipped", "reason": "technical_spec_missing"}
    return collect_foundation_executable_evidence(
        root=root,
        project_dir=project_dir,
        technical_spec=spec,
        process_isolated=True,
    )


def _artifact(result: dict[str, Any], key: str) -> dict[str, Any]:
    return dict(dict(result.get("artifact_contents") or {}).get(key) or {})


def _executor(evidence: dict[str, Any]) -> dict[str, Any]:
    summary = dict(evidence.get("summary") or {})
    reason = str(evidence.get("reason") or "")
    target = str(evidence.get("target") or "")
    if not summary and reason and target:
        summary = {
            "signal_strength": "not_measured",
            "callable_harness_count": 0,
            "skipped_reason_counts": {reason: 1},
            "skipped_targets": [{"target": target, "reason": reason}],
        }
    return {
        "test_result": {
            "executable_acceptance_result": {
                "status": evidence.get("status"),
                "summary": summary,
            }
        }
    }


def _evidence_rank(evidence: dict[str, Any]) -> int:
    summary = dict(evidence.get("summary") or {})
    if (
        evidence.get("status") == "passed"
        and summary.get("signal_strength") == "executable_callable"
        and int(summary.get("callable_harness_count") or 0) > 0
    ):
        return 3
    if evidence.get("reason") in {"side_effectful_target", "state_mutating_target"}:
        return 2
    if evidence.get("status") == "passed":
        return 1
    return 0


def _attach_feedback(
    result: dict[str, Any], evidence: dict[str, Any], history: list[dict[str, Any]]
) -> None:
    summary = dict(evidence.get("summary") or {})
    resolved = bool(
        evidence.get("status") == "passed"
        and summary.get("signal_strength") == "executable_callable"
        and int(summary.get("callable_harness_count") or 0) > 0
    )
    status = "resolved" if resolved else "iteration_limit"
    result["execution_reselection_history"] = history
    result["execution_reselection_status"] = status
    for artifact in dict(result.get("artifact_contents") or {}).values():
        if isinstance(artifact, dict):
            artifact["execution_reselection_history"] = history
            artifact["execution_reselection_status"] = status
