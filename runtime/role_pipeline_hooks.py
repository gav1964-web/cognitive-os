"""Built-in lifecycle hooks for the default role pipeline."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .architecture_analysis_document import write_architecture_analysis_document
from .cognitive_control_plane import run_cognitive_control_plane
from .contract_registry import load_artifact_contracts
from .programmer_executor import run_programmer_executor
from .role_gate_runner import run_role_gate_report
from .role_skill_common import write_role_artifact
from .technical_spec_document import write_technical_spec_document
from .transformation_flow import run_transformation_flow


def run_executor_hook(
    *,
    root: Path,
    project_dir: Path,
    technical_spec: dict[str, Any],
    implementation_plan: dict[str, Any],
    test_plan: dict[str, Any],
    task_tree: dict[str, Any],
    enabled: bool,
) -> dict[str, Any]:
    if not enabled:
        return {"status": "skipped", "reason": "run_executor flag is false"}
    result = run_programmer_executor(
        root=root,
        project_dir=project_dir,
        technical_spec=technical_spec,
        implementation_plan=implementation_plan,
        test_plan=test_plan,
        task_tree=task_tree,
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
        "no_patch_package_path": result.get("no_patch_package_path"),
        "blocked_execution_report_path": result.get("blocked_execution_report_path"),
        "test_result_path": test_result_path,
        "test_result": test_result,
        "source_code_changes": result.get("source_code_changes", False),
    }


def run_control_plane_hook(
    *,
    goal: str,
    artifacts: dict[str, dict[str, Any]],
    review: dict[str, Any],
    llm_invoked: bool,
) -> dict[str, Any]:
    return run_cognitive_control_plane(
        goal=goal,
        artifacts=artifacts,
        review=review,
        llm_invoked=llm_invoked,
    )


def run_role_gates_hook(
    *,
    artifacts: dict[str, dict[str, Any]],
    project_report: dict[str, Any],
) -> dict[str, Any]:
    return run_role_gate_report(artifacts=artifacts, project_report=project_report)


def run_artifact_writer_hook(*, root: Path, artifacts: dict[str, dict[str, Any]]) -> dict[str, Any]:
    paths = {}
    contracts = load_artifact_contracts()
    for key, artifact in artifacts.items():
        artifact_type = str(artifact.get("artifact_type") or "")
        producer = str(dict(contracts.get(artifact_type, {})).get("producer") or "unknown")
        path = write_role_artifact(root, producer, artifact)
        artifact["artifact_path"] = path.as_posix()
        paths[key] = path.as_posix()
    return {"status": "written", "paths": paths}


def run_human_document_writer_hook(
    *,
    root: Path,
    project_report: dict[str, Any],
    architecture_decision: dict[str, Any],
    technical_spec: dict[str, Any],
) -> dict[str, Any]:
    project = architecture_decision.get("project")
    report = {"content": project_report, "project": project}
    architecture_path = write_architecture_analysis_document(
        root=root,
        project_report=report,
        architecture_decision=architecture_decision,
        technical_spec=technical_spec,
        output_group="pipelines",
    )
    spec_path = write_technical_spec_document(
        root=root,
        project_report=report,
        architecture_decision=architecture_decision,
        technical_spec=technical_spec,
        output_group="pipelines",
    )
    return {
        "status": "written",
        "documents": {
            "architecture_analysis": architecture_path.as_posix(),
            "technical_spec": spec_path.as_posix(),
        },
    }


def run_transform_hook(
    *,
    root: Path,
    project_dir: Path,
    next_action: str,
    force: bool,
) -> dict[str, Any]:
    if next_action == "rework_role_artifacts":
        return {"status": "skipped", "reason": "review requires rework"}
    result = run_transformation_flow(root=root, project_dir=project_dir, force=force, promote=False)
    return {
        "status": result.get("status"),
        "kind": result.get("kind"),
        "report_path": result.get("report_path"),
        "candidate_path": result.get("candidate_path"),
        "spec_path": result.get("spec_path"),
        "selected": result.get("selected"),
    }


def run_pipeline_report_writer_hook(*, root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    out_dir = root / "artifacts" / "roles" / "pipelines"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = out_dir / f"role_pipeline_{stamp}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"status": "written", "report_path": path.as_posix()}
