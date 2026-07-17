"""Orchestrate deterministic role skills into one artifact pipeline."""

from __future__ import annotations

import json
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .architecture_analysis_document import write_architecture_analysis_document
from .cognitive_control_plane import run_cognitive_control_plane
from .contract_registry import load_artifact_contracts
from .project_benchmark import analyze_project
from .local_inference import LocalInferenceConfig
from .role_artifact_interpreter import load_role_artifact_pipeline, run_role_artifact_pipeline
from .role_skill_common import load_skill_registry, write_role_artifact
from .programmer_executor import run_programmer_executor
from .transformation_flow import run_transformation_flow


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
    with _pushd(root):
        report = analyze_project(project_dir)["project_map_report"]
    build_pipeline = _pipeline_without_review()
    artifacts = run_role_artifact_pipeline(
        goal=goal,
        project_report=report,
        architect_advisory_config=architect_advisory_config,
        pipeline=build_pipeline,
    )
    adr = artifacts["architecture_decision"]
    spec = artifacts["technical_spec"]
    implementation = artifacts["implementation_plan"]
    test_plan = artifacts["test_plan"]
    executor = _maybe_run_executor(
        root=root,
        project_dir=project_dir,
        spec=spec,
        implementation=implementation,
        test_plan=test_plan,
        run_executor=run_executor,
    )
    test_result = dict(executor.get("test_result", {})) if executor.get("test_result") else None
    review_artifacts = run_role_artifact_pipeline(
        goal=goal,
        project_report=report,
        initial_artifacts=artifacts,
        architect_advisory_config=architect_advisory_config,
        test_result=test_result,
        pipeline=_review_only_pipeline(),
    )
    review = review_artifacts["review_findings"]
    artifacts = {
        "architecture_decision": adr,
        "technical_spec": spec,
        "implementation_plan": implementation,
        "test_plan": test_plan,
        "review_findings": review,
    }
    control_plane = run_cognitive_control_plane(
        goal=goal,
        artifacts=artifacts,
        review=review,
        llm_invoked=bool(dict(adr.get("architect_advisory", {})).get("llm_invoked")),
    )
    paths = _write_artifacts(root, artifacts) if write else {}
    human_documents = _write_human_documents(root, report, adr, spec) if write else {}
    next_action = str(dict(control_plane.get("role_transition", {})).get("next_action") or _next_action(review))
    transform = _maybe_run_transform(
        root=root,
        project_dir=project_dir,
        next_action=next_action,
        run_transform=run_transform,
        force_transform=force_transform,
    )
    result = {
        "status": "ok",
        "kind": "role_pipeline",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "project": project_dir.as_posix(),
        "goal": goal,
        "recommendation": review.get("recommendation"),
        "next_action": next_action,
        "architect_advisory": adr.get("architect_advisory", {}),
        "cognitive_control_plane": control_plane,
        "role_quality": _role_quality(spec, implementation, test_plan, review),
        "artifacts": _artifact_summary(artifacts, paths),
        "human_documents": human_documents,
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
    if write:
        result["report_path"] = write_role_pipeline_report(root, result).as_posix()
    return result


def _pipeline_without_review() -> dict[str, Any]:
    pipeline = load_role_artifact_pipeline()
    return {**pipeline, "steps": [step for step in pipeline["steps"] if step.get("output_key") != "review_findings"]}


def _review_only_pipeline() -> dict[str, Any]:
    pipeline = load_role_artifact_pipeline()
    return {**pipeline, "steps": [step for step in pipeline["steps"] if step.get("output_key") == "review_findings"]}


def write_role_pipeline_report(root: Path, payload: dict[str, Any]) -> Path:
    out_dir = root / "artifacts" / "roles" / "pipelines"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = out_dir / f"role_pipeline_{stamp}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


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
    target = str(implementation_target.get("candidate") or "")
    tested = str(test_target.get("candidate") or "")
    reviewed = str(review_target.get("candidate") or "")
    return {
        "selected_extraction_candidate": selected,
        "implementation_target": target,
        "implementation_targets_extraction_candidate": bool(selected and selected == target),
        "implementation_binding_status": contract_binding.get("binding_status"),
        "implementation_has_input_contract": bool(contract_binding.get("input_contract")),
        "implementation_has_output_contract": bool(contract_binding.get("output_contract")),
        "test_target": tested,
        "test_targets_implementation_target": bool(target and tested == target),
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


def _write_artifacts(root: Path, artifacts: dict[str, dict[str, Any]]) -> dict[str, str]:
    paths = {}
    contracts = load_artifact_contracts()
    for key, artifact in artifacts.items():
        artifact_type = str(artifact.get("artifact_type") or "")
        producer = str(dict(contracts.get(artifact_type, {})).get("producer") or "unknown")
        path = write_role_artifact(root, producer, artifact)
        artifact["artifact_path"] = path.as_posix()
        paths[key] = path.as_posix()
    return paths


def _write_human_documents(
    root: Path,
    project_report: dict[str, Any],
    architecture_decision: dict[str, Any],
    technical_spec: dict[str, Any],
) -> dict[str, str]:
    path = write_architecture_analysis_document(
        root=root,
        project_report={"content": project_report, "project": architecture_decision.get("project")},
        architecture_decision=architecture_decision,
        technical_spec=technical_spec,
        output_group="pipelines",
    )
    return {"architecture_analysis": path.as_posix()}


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


def _maybe_run_transform(
    *,
    root: Path,
    project_dir: Path,
    next_action: str,
    run_transform: bool,
    force_transform: bool,
) -> dict[str, Any]:
    if not run_transform:
        return {"status": "skipped", "reason": "run_transform flag is false"}
    if next_action == "rework_role_artifacts":
        return {"status": "skipped", "reason": "review requires rework"}
    result = run_transformation_flow(root=root, project_dir=project_dir, force=force_transform, promote=False)
    return {
        "status": result.get("status"),
        "kind": result.get("kind"),
        "report_path": result.get("report_path"),
        "candidate_path": result.get("candidate_path"),
        "spec_path": result.get("spec_path"),
        "selected": result.get("selected"),
    }


def _maybe_run_executor(
    *,
    root: Path,
    project_dir: Path,
    spec: dict[str, Any],
    implementation: dict[str, Any],
    test_plan: dict[str, Any],
    run_executor: bool,
) -> dict[str, Any]:
    if not run_executor:
        return {"status": "skipped", "reason": "run_executor flag is false"}
    result = run_programmer_executor(
        root=root,
        project_dir=project_dir,
        technical_spec=spec,
        implementation_plan=implementation,
        test_plan=test_plan,
        run_verification=True,
        apply_source=False,
    )
    test_result = {}
    test_result_path = result.get("test_result_path")
    if test_result_path:
        test_result = json.loads(Path(str(test_result_path)).read_text(encoding="utf-8"))
    return {
        "status": result.get("status"),
        "execution_dir": result.get("execution_dir"),
        "patch_package_path": result.get("patch_package_path"),
        "test_result_path": test_result_path,
        "test_result": test_result,
        "source_code_changes": result.get("source_code_changes", False),
    }


@contextmanager
def _pushd(path: Path):
    previous = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)
