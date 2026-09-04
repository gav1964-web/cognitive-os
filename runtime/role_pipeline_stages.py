"""Public stage handlers for the configured role pipeline workflow."""

from __future__ import annotations

import os
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .configured_role_pipeline import artifact_by_type, configured_pipeline_phase, run_configured_role_prefix
from .role_project_analysis import analyze_role_project
from .role_artifact_interpreter import run_role_artifact_pipeline
from .role_lifecycle_interpreter import run_lifecycle_phase
from .technical_spec_policy import load_technical_spec_policy
from .architect_first_slice_reselection import reselect_architecture_first_slice
from .no_safe_candidate_recovery import run_no_safe_candidate_recovery
from .programmer_patch_synthesizer import synthesize_recovery_patch_package
from .recovery_patch_verification import verify_recovery_patch_package
from .executable_reselection import (
    build_execution_reselection_request,
    feedback_iteration_limit,
    record_rejected_target,
)


def stage_analyze(state: dict[str, Any]) -> None:
    with _pushd(state["root"]):
        state["project_report"] = analyze_role_project(root=state["root"], project_dir=state["project_dir"], goal=state["goal"])["project_map_report"]


def stage_build(state: dict[str, Any]) -> None:
    reselection = dict(load_technical_spec_policy().get("first_slice_reselection") or {})
    artifacts = run_configured_role_prefix(
        goal=state["goal"],
        project_report=state["project_report"],
        architect_advisory_config=state["architect_advisory_config"],
        until_output_key="programmer_task_tree",
        reselection_triggers={str(item) for item in reselection.get("production_triggers") or []},
    )
    _bind_build_artifacts(state, artifacts)


def _bind_build_artifacts(
    state: dict[str, Any], artifacts: dict[str, dict[str, Any]]
) -> None:
    state["artifacts"] = artifacts
    for key, artifact_type in (
        ("adr", "ArchitectureDecisionRecord"),
        ("spec", "TechnicalSpec"),
        ("implementation", "ImplementationPlan"),
        ("test_plan", "TestPlan"),
    ):
        state[key] = artifact_by_type(artifacts, artifact_type)
    state["lifecycle_context"] = {
        key: state[key]
        for key in ("root", "project_dir", "goal", "project_report", "artifacts", "run_executor", "write")
    }


def stage_after_build(state: dict[str, Any]) -> None:
    _run_executor_stage(state)
    _close_execution_reselection_loop(state)


def _run_executor_stage(state: dict[str, Any]) -> None:
    executor = run_lifecycle_phase("after_build", context=state["lifecycle_context"])["executor"]
    state["executor"] = executor
    state["test_result"] = dict(executor.get("test_result", {})) if executor.get("test_result") else None


def _close_execution_reselection_loop(state: dict[str, Any]) -> None:
    history: list[dict[str, Any]] = []
    for iteration in range(1, feedback_iteration_limit() + 1):
        request = build_execution_reselection_request(state["executor"], state["spec"])
        if request.get("status") != "required":
            break
        rejected = record_rejected_target(state["adr"], request, iteration=iteration)
        spec_with_request = dict(state["spec"])
        spec_with_request["first_slice_reselection_request"] = {
            **request,
            "status": "required",
        }
        resolution = reselect_architecture_first_slice(
            architecture_decision=rejected,
            technical_spec=spec_with_request,
            project_report=state["project_report"],
            iteration=iteration,
        )
        event = {
            "iteration": iteration,
            "rejected_target": request.get("current_target"),
            "blocking_evidence": request.get("blocking_evidence"),
            "resolution_status": resolution.get("status"),
            "selected_targets": list(dict(resolution.get("outcome") or {}).get("selected_targets") or []),
        }
        history.append(event)
        if resolution.get("status") != "selected":
            break
        artifacts = run_configured_role_prefix(
            goal=state["goal"],
            project_report=state["project_report"],
            architect_advisory_config=state["architect_advisory_config"],
            until_output_key="programmer_task_tree",
            artifact_transform=_replace_architecture_decision(
                dict(resolution.get("architecture_decision") or rejected)
            ),
        )
        _bind_build_artifacts(state, artifacts)
        _run_executor_stage(state)
    if history:
        pending = build_execution_reselection_request(state["executor"], state["spec"])
        feedback_status = "iteration_limit" if pending.get("status") == "required" else "resolved"
        state["execution_reselection_history"] = history
        state["executor"]["execution_reselection_history"] = history
        state["executor"]["execution_reselection_status"] = feedback_status
        if feedback_status == "iteration_limit":
            state["executor"]["status"] = "needs_review"
            if state.get("test_result"):
                state["test_result"]["status"] = "failed"
                summary = state["test_result"].setdefault("summary", {})
                summary["execution_reselection"] = "iteration_limit"
                state["executor"]["test_result"] = state["test_result"]
        for artifact in state["artifacts"].values():
            artifact["execution_reselection_history"] = history
            artifact["execution_reselection_status"] = feedback_status


def _replace_architecture_decision(revised: dict[str, Any]):
    def transform(artifact: dict[str, Any]) -> dict[str, Any]:
        return revised if artifact.get("artifact_type") == "ArchitectureDecisionRecord" else artifact

    return transform


def stage_review(state: dict[str, Any]) -> None:
    artifacts = run_role_artifact_pipeline(
        goal=state["goal"],
        project_report=state["project_report"],
        initial_artifacts=state["artifacts"],
        architect_advisory_config=state["architect_advisory_config"],
        test_result=state["test_result"],
        pipeline=configured_pipeline_phase("review"),
    )
    state["artifacts"] = artifacts
    state["review"] = artifact_by_type(artifacts, "ReviewFindings")


def stage_after_review(state: dict[str, Any]) -> None:
    context = state["lifecycle_context"]
    context.update(
        {
            "artifacts": state["artifacts"],
            "llm_invoked": bool(dict(state["adr"].get("architect_advisory", {})).get("llm_invoked")),
        }
    )
    outputs = run_lifecycle_phase("after_review", context=context)
    state["control_plane"] = outputs["cognitive_control_plane"]
    state["role_gates"] = outputs["role_gates"]
    state["paths"] = dict(outputs["artifact_writer"].get("paths") or {})
    state["human_documents"] = dict(outputs["human_document_writer"].get("documents") or {})
    state["no_safe_candidate_recovery"] = run_no_safe_candidate_recovery(
        project_root=state["project_dir"],
        project=state["project_dir"].name,
        technical_spec=state["spec"],
        control_plane=state["control_plane"],
    )
    _run_recovery_developer_stage(state)
    transition = dict(state["control_plane"].get("role_transition", {}))
    state["next_action"] = str(transition.get("next_action") or _next_action(state["review"]))


def _run_recovery_developer_stage(state: dict[str, Any]) -> None:
    recovery = state["no_safe_candidate_recovery"]
    if not state.get("run_executor") or recovery.get("status") != "bounded_rework_ready":
        recovery["developer_execution"] = {
            "status": "skipped",
            "reason": "run_executor flag is false"
            if not state.get("run_executor")
            else "recovery route is not ready",
        }
        return
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    execution_dir = state["root"] / "artifacts" / "programmer_executor" / f"recovery_{stamp}"
    package = synthesize_recovery_patch_package(
        execution_dir=execution_dir,
        project_dir=state["project_dir"],
        recovery_route=recovery,
    )
    if package.get("status") == "prepared":
        verification = verify_recovery_patch_package(
            project_dir=state["project_dir"],
            patch_package=package,
            verification_dir=execution_dir / "differential_verification",
        )
        package["differential_verification"] = verification
        package["verification"]["tester_differential_status"] = verification.get("status")
    recovery["developer_execution"] = package


def stage_after_decision(state: dict[str, Any]) -> None:
    context = state["lifecycle_context"]
    context.update(
        {
            "next_action": state["next_action"],
            "run_transform": state["run_transform"],
            "force_transform": state["force_transform"],
        }
    )
    state["transform"] = run_lifecycle_phase("after_decision", context=context)["transform"]


def stage_assemble_result(state: dict[str, Any]) -> None:
    adr = state["adr"]
    control_plane = state["control_plane"]
    transform = state["transform"]
    executor = state["executor"]
    state["result"] = {
        "status": "ok",
        "kind": "role_pipeline",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "project": state["project_dir"].as_posix(),
        "goal": state["goal"],
        "recommendation": state["review"].get("recommendation"),
        "next_action": state["next_action"],
        "architect_advisory": adr.get("architect_advisory", {}),
        "cognitive_control_plane": control_plane,
        "role_gates": state["role_gates"],
        "role_quality": _role_quality(state["spec"], state["implementation"], state["test_plan"], state["review"]),
        "chain_telemetry": _chain_telemetry(state),
        "no_safe_candidate_recovery": state["no_safe_candidate_recovery"],
        "artifacts": _artifact_summary(state["artifacts"], state["paths"]),
        "human_documents": state["human_documents"],
        "transform": transform,
        "executor": executor,
        "safety": {
            "source_code_changes": bool(executor.get("source_code_changes")),
            "registry_changes": False,
            "foundry_invoked": transform.get("status") in {"promotion_ready", "promoted"},
            "llm_invoked": bool(dict(adr.get("architect_advisory", {})).get("llm_invoked")),
            "l4_5_required": bool(dict(control_plane.get("semantic_escalation", {})).get("l4_5_required")),
        },
    }


def _chain_telemetry(state: dict[str, Any]) -> dict[str, Any]:
    request = dict(state["spec"].get("first_slice_reselection_request") or {})
    build_history = []
    if request.get("resolution_status"):
        build_history.append({
            "trigger": request.get("trigger"),
            "resolution_status": request.get("resolution_status"),
            "terminal": request.get("terminal"),
            "outcome": request.get("outcome"),
        })
    risks = [dict(row) for row in state["review"].get("risk_assessment", []) if isinstance(row, dict)]
    return {
        "build_reselection_history": build_history,
        "execution_reselection_history": list(state.get("execution_reselection_history") or []),
        "role_transition": dict(state["control_plane"].get("role_transition") or {}),
        "candidate_arbitration": dict(
            dict(state["spec"].get("extraction_contract") or {}).get("candidate_advisory") or {}
        ),
        "no_safe_candidate_recovery": {
            "status": state["no_safe_candidate_recovery"].get("status"),
            "route": list(state["no_safe_candidate_recovery"].get("route") or []),
            "architect_gate_status": dict(
                state["no_safe_candidate_recovery"].get("architect_reentry_gate") or {}
            ).get("status"),
            "candidate_status": dict(
                state["no_safe_candidate_recovery"].get("provisional_candidate") or {}
            ).get("status"),
            "developer_execution_status": dict(
                state["no_safe_candidate_recovery"].get("developer_execution") or {}
            ).get("status"),
        },
        "review_risk_summary": {
            "controlled": sum(row.get("disposition") == "controlled_by_verified_plan" for row in risks),
            "requires_human_review": sum(row.get("disposition") == "requires_human_review" for row in risks),
            "requires_rework": sum(row.get("disposition") == "requires_rework" for row in risks),
        },
    }


def stage_after_result(state: dict[str, Any]) -> None:
    state["lifecycle_context"]["result"] = state["result"]
    report_writer = run_lifecycle_phase("after_result", context=state["lifecycle_context"])["pipeline_report_writer"]
    if report_writer.get("report_path"):
        state["result"]["report_path"] = report_writer["report_path"]


def _role_quality(
    spec: dict[str, Any],
    implementation: dict[str, Any],
    test_plan: dict[str, Any],
    review: dict[str, Any],
) -> dict[str, Any]:
    extraction_contract = dict(spec.get("extraction_contract", {}))
    implementation_target = dict(implementation.get("implementation_target", {}))
    contract_binding = dict(implementation.get("contract_binding", {}))
    test_target = dict(test_plan.get("test_target", {}))
    coverage = dict(review.get("coverage_assessment", {}))
    review_target = dict(review.get("review_target", {}))
    selected = str(extraction_contract.get("candidate") or "")
    implementation_blocked = contract_binding.get("binding_status") == "blocked_no_safe_candidate"
    test_blocked = test_plan.get("status") == "blocked_no_safe_candidate"
    target = str(implementation_target.get("candidate") or ("blocked_no_safe_candidate" if implementation_blocked else ""))
    tested = str(test_target.get("candidate") or ("blocked_no_safe_candidate" if test_blocked else ""))
    reviewed = str(review_target.get("candidate") or "")
    return {
        "selected_extraction_candidate": selected,
        "implementation_target": target,
        "implementation_targets_extraction_candidate": bool(selected and selected == target),
        "implementation_binding_status": contract_binding.get("binding_status"),
        "implementation_blocked_no_safe_candidate": implementation_blocked,
        "implementation_has_input_contract": isinstance(contract_binding.get("input_contract"), dict),
        "implementation_has_output_contract": bool(contract_binding.get("output_contract")),
        "test_target": tested,
        "test_targets_implementation_target": bool(target and tested == target),
        "test_blocked_no_safe_candidate": test_blocked,
        "test_has_contract_matrix": bool(test_plan.get("contract_test_matrix")),
        "test_has_negative_tests_for_target": _rows_cover_target(test_plan.get("negative_tests", []), target),
        "review_target": reviewed,
        "review_targets_implementation_target": bool(target and reviewed == target),
        "review_confirms_target_coverage": coverage.get("target_covered") is True,
        "review_contract_violations": len(review.get("contract_violations", [])),
    }


def _rows_cover_target(rows: object, target: str) -> bool:
    return bool(
        target
        and isinstance(rows, list)
        and any(isinstance(row, dict) and row.get("target") == target for row in rows)
    )


def _artifact_summary(artifacts: dict[str, dict[str, Any]], paths: dict[str, str]) -> dict[str, dict[str, Any]]:
    return {
        key: {
            "artifact_type": artifact.get("artifact_type"),
            "role": artifact.get("role"),
            "status": artifact.get("status"),
            "path": paths.get(key),
        }
        for key, artifact in artifacts.items()
    }


def _next_action(review: dict[str, Any]) -> str:
    recommendation = review.get("recommendation")
    if recommendation == "request_rework":
        return "rework_role_artifacts"
    if recommendation == "approve_with_risks":
        return "review_risks_then_run_project_transform"
    return "run_project_transform"


@contextmanager
def _pushd(path: Path):
    previous = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)
