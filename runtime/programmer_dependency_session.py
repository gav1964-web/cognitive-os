"""Adapter between Programmer Executor strategy artifacts and dependency sessions."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .dependency_probe_session import run_dependency_probe_session
from .programmer_verification import run_test_result


def run_executor_dependency_session(
    *, root: Path, strategy: dict[str, Any], approval: dict[str, Any] | None,
) -> dict[str, Any]:
    if not approval:
        return {}
    boundary = dict(strategy.get("dependency_boundary_profile") or {})
    profile = dict(boundary.get("isolated_environment_profile") or {})
    if not profile:
        return {
            "artifact_type": "DependencyProbeSessionResult",
            "status": "blocked",
            "reason": "profile_unavailable",
        }
    return run_dependency_probe_session(
        workspace_root=root,
        initial_profile=profile,
        session=dict(approval),
    )


def run_dependency_environment_verification(
    *, root: Path, project_dir: Path, source_project_dir: Path,
    implementation_plan: dict[str, Any], test_plan: dict[str, Any], execution_dir: Path,
    session_result: dict[str, Any], run_verification: bool, max_commands: int,
) -> dict[str, Any]:
    if session_result.get("status") != "passed":
        return {}
    python = Path(str(dict(session_result.get("verified_environment") or {}).get("python") or ""))
    if not python.is_file():
        return {
            "artifact_type": "TestResult",
            "status": "failed",
            "reason": "verified_environment_python_unavailable",
        }
    result = run_test_result(
        root=root,
        project_dir=project_dir,
        source_project_dir=source_project_dir,
        implementation_plan=implementation_plan,
        test_plan=test_plan,
        execution_dir=execution_dir / "dependency_environment_verification",
        run_verification=run_verification,
        max_commands=max_commands,
        python_executable=python,
    )
    acceptance = dict(result.get("executable_acceptance_result") or {})
    summary = dict(acceptance.get("summary") or {})
    if int(summary.get("callable_harness_count") or 0) < 1:
        result["status"] = "failed"
        result["reason"] = "dependency_environment_did_not_unlock_callable"
    return result
