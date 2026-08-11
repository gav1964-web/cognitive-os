"""Orchestrate deterministic role skills into one artifact pipeline."""

from __future__ import annotations

import os
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .configured_role_pipeline import artifact_by_type, configured_pipeline_phase
from .project_benchmark import analyze_project
from .local_inference import LocalInferenceConfig
from .role_artifact_interpreter import run_role_artifact_pipeline
from .role_lifecycle_interpreter import run_lifecycle_phase
from .role_skill_common import load_skill_registry
from .role_workflow_interpreter import run_configured_workflow


def run_role_pipeline(
    *,
    root: Path,
    project_dir: Path,
    goal: str,
    write: bool = False,
    run_transform: bool = False,
    run_executor: bool = False,
    force_transform: bool = False,
    architect_advisory_config: LocalInferenceConfig | None = None,
) -> dict[str, Any]:
    load_skill_registry(root)
    state = {
        "root": root,
        "project_dir": project_dir,
        "goal": goal,
        "write": write,
        "run_transform": run_transform,
        "run_executor": run_executor,
        "force_transform": force_transform,
        "architect_advisory_config": architect_advisory_config,
    }
    run_configured_workflow(state=state)
    return dict(state["result"])


def _stage_analyze(state: dict[str, Any]) -> None:
    with _pushd(state["root"]):
        state["project_report"] = analyze_project(state["project_dir"])["project_map_report"]


def _stage_build(state: dict[str, Any]) -> None:
    artifacts = run_role_artifact_pipeline(
        goal=state["goal"],
        project_report=state["project_report"],
        architect_advisory_config=state["architect_advisory_config"],
        pipeline=configured_pipeline_phase("build"),
    )
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


def _stage_after_build(state: dict[str, Any]) -> None:
    executor = run_lifecycle_phase("after_build", context=state["lifecycle_context"])["executor"]
    state["executor"] = executor
    state["test_result"] = dict(executor.get("test_result", {})) if executor.get("test_result") else None


def _stage_review(state: dict[str, Any]) -> None:
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


def _stage_after_review(state: dict[str, Any]) -> None:
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
    transition = dict(state["control_plane"].get("role_transition", {}))
    state["next_action"] = str(transition.get("next_action") or _next_action(state["review"]))


def _stage_after_decision(state: dict[str, Any]) -> None:
    context = state["lifecycle_context"]
    context.update(
        {
            "next_action": state["next_action"],
            "run_transform": state["run_transform"],
            "force_transform": state["force_transform"],
        }
    )
    state["transform"] = run_lifecycle_phase("after_decision", context=context)["transform"]


def _stage_assemble_result(state: dict[str, Any]) -> None:
    adr = state["adr"]
    control_plane = state["control_plane"]
    transform = state["transform"]
    executor = state["executor"]
    project_dir = state["project_dir"]
    result = {
        "status": "ok",
        "kind": "role_pipeline",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "project": project_dir.as_posix(),
        "goal": state["goal"],
        "recommendation": state["review"].get("recommendation"),
        "next_action": state["next_action"],
        "architect_advisory": adr.get("architect_advisory", {}),
        "cognitive_control_plane": control_plane,
        "role_gates": state["role_gates"],
        "role_quality": _role_quality(state["spec"], state["implementation"], state["test_plan"], state["review"]),
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
    state["result"] = result


def _stage_after_result(state: dict[str, Any]) -> None:
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
