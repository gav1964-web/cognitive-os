"""Allowed verification command runner for sandbox Programmer artifacts."""

from __future__ import annotations

import ast
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .executable_acceptance import run_executable_acceptance


def run_test_result(
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
    command_results = _command_results(root, project_dir, implementation_plan, run_verification, max_commands)
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
        "created_at": datetime.now(timezone.utc).isoformat(),
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


def _command_results(
    root: Path,
    project_dir: Path,
    implementation_plan: dict[str, Any],
    run_verification: bool,
    max_commands: int,
) -> list[dict[str, Any]]:
    commands = [str(item) for item in implementation_plan.get("verification_commands", []) if item]
    results = [{"command": None, "status": "skipped", "reason": "run_verification=false"}] if not run_verification else [
        _run_project_scoped_verification(project_dir, implementation_plan)
    ]
    if not run_verification:
        return results
    for command in commands[:max_commands]:
        if _redundant_unscoped_compileall(command, implementation_plan):
            results.append({"command": command, "status": "skipped", "reason": "redundant_unscoped_compileall_replaced_by_project_scoped_check"})
            continue
        if not command_allowed(command):
            results.append({"command": command, "status": "skipped", "reason": "not in executor allowlist"})
            continue
        results.append(run_command(command, _command_cwd(command, root, project_dir)))
    return results


def _run_project_scoped_verification(project_dir: Path, implementation_plan: dict[str, Any]) -> dict[str, Any]:
    files = []
    for file_name in _expected_files(implementation_plan):
        path = (project_dir / file_name).resolve()
        try:
            path.relative_to(project_dir.resolve())
        except ValueError:
            return {"command": "project_scoped_py_compile", "status": "failed", "reason": "expected_file_outside_execution_project", "file": file_name}
        if path.suffix == ".py" and path.is_file():
            files.append(file_name)
    if not files:
        return {"command": "project_scoped_py_compile", "status": "skipped", "reason": "no_python_expected_files"}
    failures = []
    for file_name in files:
        try:
            ast.parse((project_dir / file_name).read_text(encoding="utf-8"), filename=file_name)
        except SyntaxError as exc:
            failures.append(f"{file_name}:{exc.lineno}:{exc.msg}")
    return {
        "command": "project_scoped_syntax_check",
        "kind": "project_scoped_py_compile",
        "scope": files,
        "status": "failed" if failures else "passed",
        "returncode": 1 if failures else 0,
        "stdout_tail": "",
        "stderr_tail": "\n".join(failures)[-2000:],
    }


def run_command(command: str, cwd: Path) -> dict[str, Any]:
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


def command_allowed(command: str) -> bool:
    normalized = " ".join(command.strip().split()).lower()
    return (
        normalized.startswith(f"{Path(sys.executable).as_posix().lower()} -m compileall")
        or normalized.startswith("python -m compileall")
        or (normalized.startswith("python tools/mvp_acceptance.py") and "--skip-pytest" in normalized)
        or (normalized.startswith("python -m pytest") and "tests/runtime/" in normalized.replace("\\", "/"))
    )


def _command_cwd(command: str, root: Path, project_dir: Path) -> Path:
    normalized = " ".join(command.strip().split()).lower()
    if normalized.startswith("python tools/"):
        return root
    return project_dir


def _redundant_unscoped_compileall(command: str, implementation_plan: dict[str, Any]) -> bool:
    normalized = " ".join(command.strip().split()).lower().replace("\\", "/")
    return bool(_expected_files(implementation_plan)) and normalized in {"python -m compileall .", f"{Path(sys.executable).as_posix().lower()} -m compileall ."}


def _expected_files(implementation_plan: dict[str, Any]) -> list[str]:
    files = []
    for item in implementation_plan.get("expected_files", []):
        path = str(item).split(":", 1)[0]
        if path and path not in files:
            files.append(path)
    return files[:8]
