"""Programmer executor MVP: sandbox an ImplementationPlan and emit TestResult."""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .programmer_candidate_flow import prepare_candidate_synthesis
from .programmer_dependency_session import (
    run_dependency_environment_verification,
    run_executor_dependency_session,
)
from .programmer_patch_synthesizer import synthesize_patch_package
from .programmer_patch_strategy import build_patch_strategy, llm_strategy_enabled
from .programmer_repair_loop import run_bounded_repairs
from .programmer_task_tree import build_programmer_task_tree
from .programmer_acceptance_gate import enforce_prepared_patch_acceptance, repair_needed
from .programmer_verification import run_test_result


def run_programmer_executor(
    *,
    root: Path,
    project_dir: Path,
    technical_spec: dict[str, Any],
    implementation_plan: dict[str, Any],
    test_plan: dict[str, Any],
    task_tree: dict[str, Any] | None = None,
    run_verification: bool = True,
    apply_source: bool = False,
    max_commands: int = 3,
    dependency_probe_session_approval: dict[str, Any] | None = None,
    execution_base_dir: Path | None = None,
) -> dict[str, Any]:
    target = dict(implementation_plan.get("implementation_target", {}))
    if target.get("status") == "blocked_no_safe_candidate":
        return _blocked_result(
            root,
            project_dir,
            technical_spec,
            implementation_plan,
            test_plan,
            "blocked_no_safe_candidate",
            task_tree,
        )
    if apply_source:
        return _blocked_result(root, project_dir, technical_spec, implementation_plan, test_plan, "source_edit_apply_not_enabled_in_mvp", task_tree)

    execution_dir = _execution_dir(root, base_dir=execution_base_dir)
    execution_dir.mkdir(parents=True, exist_ok=True)
    task_tree = task_tree or build_programmer_task_tree(
        technical_spec=technical_spec,
        implementation_plan=implementation_plan,
        test_plan=test_plan,
    )
    task_tree_path = _write_json(execution_dir / "task_tree.json", task_tree)
    snapshot = _snapshot_writable_files(execution_dir, project_dir, implementation_plan)
    synthesis = synthesize_patch_package(
        execution_dir=execution_dir,
        project_dir=project_dir,
        implementation_plan=implementation_plan,
        test_plan=test_plan,
    )
    execution_project_dir = Path(str(synthesis.get("sandbox_project") or project_dir))
    strategy = build_patch_strategy(
        project_dir=execution_project_dir,
        technical_spec=technical_spec,
        implementation_plan=implementation_plan,
        test_plan=test_plan,
        synthesis=synthesis,
        use_l45_llm=llm_strategy_enabled(),
    )
    synthesis, execution_project_dir, candidate_attempt = prepare_candidate_synthesis(
        execution_dir=execution_dir, project_dir=project_dir, implementation_plan=implementation_plan, synthesis=synthesis, strategy=strategy
    )
    test_result = run_test_result(
        root=root,
        project_dir=execution_project_dir,
        source_project_dir=project_dir,
        implementation_plan=implementation_plan,
        test_plan=test_plan,
        execution_dir=execution_dir,
        run_verification=run_verification,
        max_commands=max_commands,
    )
    enforce_prepared_patch_acceptance(test_result, synthesis, implementation_plan)
    test_result["programmer_task_tree"] = task_tree
    test_result["sandbox_candidate_attempt"] = candidate_attempt
    repair = run_bounded_repairs(
        root=root, source_project_dir=project_dir, execution_project_dir=execution_project_dir,
        execution_dir=execution_dir, implementation_plan=implementation_plan, test_plan=test_plan,
        test_result=test_result, synthesis=synthesis, candidate_attempt=candidate_attempt,
        run_verification=run_verification, max_commands=max_commands, should_repair=_repair_needed,
    )
    synthesis = dict(repair["synthesis"])
    execution_project_dir = Path(repair["execution_project_dir"])
    test_result = dict(repair["test_result"])
    repair_strategies = list(repair["repair_strategies"])
    repair_attempts = list(repair["repair_attempts"])
    repair_attempt = repair_attempts[-1] if repair_attempts else {
        "status": "not_attempted", "reason": "first_verification_not_failed_or_candidate_not_applied"
    }
    test_result["programmer_task_tree"] = task_tree
    test_result["sandbox_candidate_attempt"] = candidate_attempt
    test_result["sandbox_candidate_repair_attempt"] = repair_attempt
    test_result["sandbox_candidate_repair_attempts"] = repair_attempts
    if repair_strategies:
        test_result["executor_repair_strategy"] = repair_strategies[-1]
        test_result["executor_repair_strategies"] = repair_strategies
    final_strategy = build_patch_strategy(
        project_dir=execution_project_dir,
        technical_spec=technical_spec,
        implementation_plan=implementation_plan,
        test_plan=test_plan,
        synthesis=synthesis,
        acceptance_summary=dict(dict(test_result.get("executable_acceptance_result") or {}).get("summary") or {}),
        use_l45_llm=llm_strategy_enabled(),
    )
    test_result["executor_strategy"] = final_strategy
    dependency_session = run_executor_dependency_session(
        root=root, strategy=final_strategy, approval=dependency_probe_session_approval,
    )
    dependency_session_path = None
    if dependency_session:
        test_result["dependency_probe_session_result"] = dependency_session
        dependency_session_path = _write_json(
            execution_dir / "dependency_probe_session_result.json", dependency_session,
        )
        dependency_verification = run_dependency_environment_verification(
            root=root,
            project_dir=execution_project_dir,
            source_project_dir=project_dir,
            implementation_plan=implementation_plan,
            test_plan=test_plan,
            execution_dir=execution_dir,
            session_result=dependency_session,
            run_verification=run_verification,
            max_commands=max_commands,
        )
        if dependency_verification:
            test_result["dependency_environment_verification"] = dependency_verification
            test_result["summary"]["dependency_environment_verification"] = dependency_verification.get("status")
            if dependency_verification.get("status") != "ok":
                test_result["status"] = "failed"
    rebind_request = dict(final_strategy.get("contract_rebind_request") or {})
    rebind_path = _write_json(execution_dir / "contract_rebind_request.json", rebind_request) if rebind_request else None
    patch_package = _patch_package(project_dir, technical_spec, implementation_plan, test_plan, snapshot, synthesis, strategy, task_tree)
    patch_package["sandbox_candidate_attempt"] = candidate_attempt
    patch_package["sandbox_candidate_repair_attempt"] = repair_attempt
    patch_package["sandbox_candidate_repair_attempts"] = repair_attempts
    if repair_strategies:
        patch_package["executor_repair_strategy"] = repair_strategies[-1]
        patch_package["executor_repair_strategies"] = repair_strategies
    patch_path = _write_json(execution_dir / "patch_package.json", patch_package)
    test_result["patch_package_path"] = patch_path.as_posix()
    test_result["task_tree_path"] = task_tree_path.as_posix()
    test_result_path = _write_json(execution_dir / "test_result.json", test_result)
    result = {
        "status": test_result["status"],
        "kind": "programmer_executor_result",
        "created_at": _now(),
        "project": project_dir.as_posix(),
        "execution_project": execution_project_dir.as_posix(),
        "execution_dir": execution_dir.as_posix(),
        "task_tree_path": task_tree_path.as_posix(),
        "patch_package_path": patch_path.as_posix(),
        "test_result_path": test_result_path.as_posix(),
        "contract_rebind_request_path": rebind_path.as_posix() if rebind_path else None,
        "dependency_probe_session_result_path": (
            dependency_session_path.as_posix() if dependency_session_path else None
        ),
        "source_code_changes": False,
        "registry_changes": False,
        "apply_source": False,
        "reviewer_handoff": {
            "test_result": test_result_path.as_posix(),
            "next_role": "reviewer",
            "reason": "Reviewer can consume this TestResult with the original TechnicalSpec, ImplementationPlan and TestPlan.",
            "contract_rebind_request": rebind_path.as_posix() if rebind_path else None,
        },
    }
    _write_json(execution_dir / "result.json", result)
    return result


def _blocked_result(
    root: Path,
    project_dir: Path,
    technical_spec: dict[str, Any],
    implementation_plan: dict[str, Any],
    test_plan: dict[str, Any],
    reason: str,
    task_tree: dict[str, Any] | None = None,
) -> dict[str, Any]:
    execution_dir = _execution_dir(root)
    execution_dir.mkdir(parents=True, exist_ok=True)
    task_tree = task_tree or build_programmer_task_tree(
        technical_spec=technical_spec,
        implementation_plan=implementation_plan,
        test_plan=test_plan,
    )
    no_patch = _no_patch_package(project_dir, technical_spec, implementation_plan, test_plan, reason, task_tree)
    blocked_report = _blocked_execution_report(project_dir, implementation_plan, test_plan, reason)
    task_tree_path = _write_json(execution_dir / "task_tree.json", task_tree)
    no_patch_path = _write_json(execution_dir / "no_patch_package.json", no_patch)
    blocked_report_path = _write_json(execution_dir / "blocked_execution_report.json", blocked_report)
    result = {
        "status": "blocked",
        "kind": "programmer_executor_result",
        "created_at": _now(),
        "project": project_dir.as_posix(),
        "execution_dir": execution_dir.as_posix(),
        "reason": reason,
        "implementation_target": implementation_plan.get("implementation_target", {}),
        "task_tree_path": task_tree_path.as_posix(),
        "no_patch_package_path": no_patch_path.as_posix(),
        "blocked_execution_report_path": blocked_report_path.as_posix(),
        "source_code_changes": False,
        "registry_changes": False,
        "reviewer_handoff": {
            "next_role": "reviewer",
            "test_result": None,
            "no_patch_package": no_patch_path.as_posix(),
            "blocked_execution_report": blocked_report_path.as_posix(),
            "reason": "Reviewer can verify that no patch was produced and the blocked handoff was preserved.",
        },
    }
    result["result_path"] = _write_json(execution_dir / "result.json", result).as_posix()
    return result


def _no_patch_package(
    project_dir: Path,
    technical_spec: dict[str, Any],
    implementation_plan: dict[str, Any],
    test_plan: dict[str, Any],
    reason: str,
    task_tree: dict[str, Any],
) -> dict[str, Any]:
    return {
        "artifact_type": "NoPatchPackage",
        "status": "blocked",
        "created_at": _now(),
        "project": project_dir.as_posix(),
        "reason": reason,
        "source_code_changes": False,
        "registry_changes": False,
        "source_artifacts": [
            {"type": technical_spec.get("artifact_type"), "role": technical_spec.get("role")},
            {"type": implementation_plan.get("artifact_type"), "role": implementation_plan.get("role")},
            {"type": test_plan.get("artifact_type"), "role": test_plan.get("role")},
        ],
        "implementation_target": implementation_plan.get("implementation_target", {}),
        "patch_intent": implementation_plan.get("patch_intent", {}),
        "programmer_task_tree": task_tree,
        "patches": [],
        "policy": {"patch_generation_allowed": False, "apply_source_enabled": False},
    }


def _blocked_execution_report(
    project_dir: Path,
    implementation_plan: dict[str, Any],
    test_plan: dict[str, Any],
    reason: str,
) -> dict[str, Any]:
    return {
        "artifact_type": "BlockedExecutionReport",
        "role": "programmer_executor",
        "status": "blocked",
        "created_at": _now(),
        "project": project_dir.as_posix(),
        "reason": reason,
        "implementation_target": implementation_plan.get("implementation_target", {}),
        "test_plan_status": test_plan.get("status"),
        "blocked_contract_rows": _blocked_contract_rows(test_plan),
        "source_code_changes": False,
        "registry_changes": False,
        "next_role": "reviewer",
    }


def _snapshot_writable_files(execution_dir: Path, project_dir: Path, implementation_plan: dict[str, Any]) -> list[dict[str, Any]]:
    snapshot_dir = execution_dir / "source_snapshot"
    copied = []
    for file_name in _expected_files(implementation_plan):
        source = (project_dir / file_name).resolve()
        try:
            source.relative_to(project_dir.resolve())
        except ValueError:
            copied.append({"file": file_name, "status": "blocked_outside_project"})
            continue
        if not source.is_file():
            copied.append({"file": file_name, "status": "missing"})
            continue
        destination = snapshot_dir / file_name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        copied.append({"file": file_name, "status": "copied", "snapshot": destination.as_posix()})
    return copied


def _patch_package(
    project_dir: Path,
    technical_spec: dict[str, Any],
    implementation_plan: dict[str, Any],
    test_plan: dict[str, Any],
    snapshot: list[dict[str, Any]],
    synthesis: dict[str, Any],
    strategy: dict[str, Any],
    task_tree: dict[str, Any],
) -> dict[str, Any]:
    return {
        "artifact_type": "PatchPackage",
        "status": "prepared",
        "created_at": _now(),
        "project": project_dir.as_posix(),
        "mode": "isolated_sandbox_no_source_edit",
        "source_code_changes": False,
        "registry_changes": False,
        "source_artifacts": [
            {"type": technical_spec.get("artifact_type"), "role": technical_spec.get("role")},
            {"type": implementation_plan.get("artifact_type"), "role": implementation_plan.get("role")},
            {"type": test_plan.get("artifact_type"), "role": test_plan.get("role")},
        ],
        "implementation_target": implementation_plan.get("implementation_target", {}),
        "implementation_blueprint": implementation_plan.get("implementation_blueprint", {}),
        "patch_intent": implementation_plan.get("patch_intent", {}),
        "executor_handoff": implementation_plan.get("executor_handoff", {}),
        "writable_scope": implementation_plan.get("writable_scope", []),
        "expected_files": implementation_plan.get("expected_files", []),
        "programmer_task_tree": task_tree,
        "snapshot": snapshot,
        "patch_strategy": strategy,
        "patch_synthesis": {
            "status": synthesis.get("status"),
            "reason": synthesis.get("reason"),
            "sandbox_project": synthesis.get("sandbox_project"),
            "reducer_selection": synthesis.get("reducer_selection"),
        },
        "patches": synthesis.get("patches", []),
        "policy": {
            "source_edit_requires_explicit_flag": True,
            "apply_source_enabled": False,
            "rollback_source": "source_snapshot",
        },
    }

def _blocked_contract_rows(test_plan: dict[str, Any]) -> list[Any]:
    return [row for row in list(test_plan.get("contract_test_matrix", [])) if dict(row).get("direction") == "blocked_handoff"]


def _repair_needed(
    test_result: dict[str, Any],
    candidate_attempt: dict[str, Any],
    implementation_plan: dict[str, Any] | None = None,
) -> bool:
    return repair_needed(
        test_result,
        candidate_attempt,
        implementation_plan,
        llm_enabled=llm_strategy_enabled,
    )


def _expected_files(implementation_plan: dict[str, Any]) -> list[str]:
    files = []
    for item in implementation_plan.get("expected_files", []):
        path = str(item).split(":", 1)[0]
        if path and path not in files:
            files.append(path)
    return files[:8]


def _execution_dir(root: Path, *, base_dir: Path | None = None) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    parent = base_dir or root / "artifacts" / "programmer_executor"
    return parent / f"execution_{stamp}"


def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
