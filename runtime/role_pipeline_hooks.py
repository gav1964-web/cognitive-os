"""Built-in lifecycle hooks for the default role pipeline."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .cognitive_control_plane import run_cognitive_control_plane
from .programmer_executor import run_programmer_executor
from .role_gate_runner import run_role_gate_report


def run_executor_hook(
    *,
    root: Path,
    project_dir: Path,
    technical_spec: dict[str, Any],
    implementation_plan: dict[str, Any],
    test_plan: dict[str, Any],
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
