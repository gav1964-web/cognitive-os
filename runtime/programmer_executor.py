"""Programmer executor MVP: sandbox an ImplementationPlan and emit TestResult."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .executable_acceptance import run_executable_acceptance
from .programmer_patch_synthesizer import synthesize_patch_package


def run_programmer_executor(
    *,
    root: Path,
    project_dir: Path,
    technical_spec: dict[str, Any],
    implementation_plan: dict[str, Any],
    test_plan: dict[str, Any],
    run_verification: bool = True,
    apply_source: bool = False,
    max_commands: int = 3,
) -> dict[str, Any]:
    target = dict(implementation_plan.get("implementation_target", {}))
    if target.get("status") == "blocked_no_safe_candidate":
        return _blocked_result(root, project_dir, implementation_plan, "blocked_no_safe_candidate")
    if apply_source:
        return _blocked_result(root, project_dir, implementation_plan, "source_edit_apply_not_enabled_in_mvp")

    execution_dir = _execution_dir(root)
    execution_dir.mkdir(parents=True, exist_ok=True)
    snapshot = _snapshot_writable_files(execution_dir, project_dir, implementation_plan)
    synthesis = synthesize_patch_package(
        execution_dir=execution_dir,
        project_dir=project_dir,
        implementation_plan=implementation_plan,
        test_plan=test_plan,
    )
    execution_project_dir = Path(str(synthesis.get("sandbox_project") or project_dir))
    patch_package = _patch_package(project_dir, technical_spec, implementation_plan, test_plan, snapshot, synthesis)
    patch_path = _write_json(execution_dir / "patch_package.json", patch_package)
    test_result = _run_test_result(
        root=root,
        project_dir=execution_project_dir,
        source_project_dir=project_dir,
        implementation_plan=implementation_plan,
        test_plan=test_plan,
        execution_dir=execution_dir,
        run_verification=run_verification,
        max_commands=max_commands,
    )
    test_result["patch_package_path"] = patch_path.as_posix()
    test_result_path = _write_json(execution_dir / "test_result.json", test_result)
    result = {
        "status": test_result["status"],
        "kind": "programmer_executor_result",
        "created_at": _now(),
        "project": project_dir.as_posix(),
        "execution_project": execution_project_dir.as_posix(),
        "execution_dir": execution_dir.as_posix(),
        "patch_package_path": patch_path.as_posix(),
        "test_result_path": test_result_path.as_posix(),
        "source_code_changes": False,
        "registry_changes": False,
        "apply_source": False,
        "reviewer_handoff": {
            "test_result": test_result_path.as_posix(),
            "next_role": "reviewer",
            "reason": "Reviewer can consume this TestResult with the original TechnicalSpec, ImplementationPlan and TestPlan.",
        },
    }
    _write_json(execution_dir / "result.json", result)
    return result


def _blocked_result(root: Path, project_dir: Path, implementation_plan: dict[str, Any], reason: str) -> dict[str, Any]:
    execution_dir = _execution_dir(root)
    execution_dir.mkdir(parents=True, exist_ok=True)
    result = {
        "status": "blocked",
        "kind": "programmer_executor_result",
        "created_at": _now(),
        "project": project_dir.as_posix(),
        "execution_dir": execution_dir.as_posix(),
        "reason": reason,
        "implementation_target": implementation_plan.get("implementation_target", {}),
        "source_code_changes": False,
        "registry_changes": False,
        "reviewer_handoff": {"next_role": "reviewer", "test_result": None},
    }
    result["result_path"] = _write_json(execution_dir / "result.json", result).as_posix()
    return result


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
        "snapshot": snapshot,
        "patch_synthesis": {
            "status": synthesis.get("status"),
            "reason": synthesis.get("reason"),
            "sandbox_project": synthesis.get("sandbox_project"),
        },
        "patches": synthesis.get("patches", []),
        "policy": {
            "source_edit_requires_explicit_flag": True,
            "apply_source_enabled": False,
            "rollback_source": "source_snapshot",
        },
    }


def _run_test_result(
    *,
    root: Path,
    project_dir: Path,
    source_project_dir: Path,
    implementation_plan: dict[str, Any],
    test_plan: dict[str, Any],
    execution_dir: Path,
    run_verification: bool,
    max_commands: int,
) -> dict[str, Any]:
    commands = [str(item) for item in implementation_plan.get("verification_commands", []) if item]
    command_results = []
    if not run_verification:
        command_results.append({"command": None, "status": "skipped", "reason": "run_verification=false"})
    else:
        command_results.append(_run_project_scoped_verification(project_dir, implementation_plan))
        for command in commands[:max_commands]:
            if not _command_allowed(command):
                command_results.append({"command": command, "status": "skipped", "reason": "not in executor allowlist"})
                continue
            command_results.append(_run_command(command, root))
    failed = [item for item in command_results if item.get("status") == "failed"]
    executed = [item for item in command_results if item.get("status") in {"passed", "failed"}]
    executable_acceptance = run_executable_acceptance(
        root=root,
        project_dir=project_dir,
        test_plan=test_plan,
        work_dir=execution_dir,
    )
    if executable_acceptance.get("status") == "failed":
        failed.append({"status": "failed", "command": "executable_acceptance"})
    return {
        "artifact_type": "TestResult",
        "role": "programmer_executor",
        "status": "failed" if failed else "ok",
        "created_at": _now(),
        "project": source_project_dir.as_posix(),
        "execution_project": project_dir.as_posix(),
        "implementation_target": implementation_plan.get("implementation_target", {}),
        "commands": command_results,
        "summary": {
            "executed": len(executed),
            "passed": sum(1 for item in executed if item.get("status") == "passed"),
            "failed": len(failed),
            "skipped": sum(1 for item in command_results if item.get("status") == "skipped"),
            "executable_acceptance": executable_acceptance.get("status"),
        },
        "executable_acceptance_result": executable_acceptance,
        "source_code_changes": False,
        "registry_changes": False,
    }


def _run_project_scoped_verification(project_dir: Path, implementation_plan: dict[str, Any]) -> dict[str, Any]:
    files = []
    for file_name in _expected_files(implementation_plan):
        path = (project_dir / file_name).resolve()
        try:
            path.relative_to(project_dir.resolve())
        except ValueError:
            return {
                "command": "project_scoped_py_compile",
                "status": "failed",
                "reason": "expected_file_outside_execution_project",
                "file": file_name,
            }
        if path.suffix == ".py" and path.is_file():
            files.append(file_name)
    if not files:
        return {
            "command": "project_scoped_py_compile",
            "status": "skipped",
            "reason": "no_python_expected_files",
        }
    command = f"{Path(sys.executable).as_posix()} -m py_compile " + " ".join(files)
    result = _run_command(command, project_dir)
    result["kind"] = "project_scoped_py_compile"
    result["scope"] = files
    return result


def _run_command(command: str, cwd: Path) -> dict[str, Any]:
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    result = subprocess.run(
        command,
        cwd=str(cwd),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
        encoding="utf-8",
        errors="replace",
        timeout=180,
    )
    return {
        "command": command,
        "status": "passed" if result.returncode == 0 else "failed",
        "returncode": result.returncode,
        "stdout_tail": result.stdout[-2000:],
        "stderr_tail": result.stderr[-2000:],
    }


def _command_allowed(command: str) -> bool:
    normalized = " ".join(command.strip().split()).lower()
    if normalized.startswith(f"{Path(sys.executable).as_posix().lower()} -m compileall"):
        return True
    if normalized.startswith("python -m compileall"):
        return True
    if normalized.startswith("python tools/mvp_acceptance.py") and "--skip-pytest" in normalized:
        return True
    if normalized.startswith("python -m pytest") and "tests/runtime/" in normalized.replace("\\", "/"):
        return True
    return False


def _expected_files(implementation_plan: dict[str, Any]) -> list[str]:
    files = []
    for item in implementation_plan.get("expected_files", []):
        path = str(item).split(":", 1)[0]
        if path and path not in files:
            files.append(path)
    return files[:8]


def _execution_dir(root: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return root / "artifacts" / "programmer_executor" / f"execution_{stamp}"


def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
