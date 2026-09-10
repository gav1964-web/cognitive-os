"""Allowed verification command runner for sandbox Programmer artifacts."""

from __future__ import annotations

import os
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .executable_acceptance import run_executable_acceptance
from .python_parser_compatibility import parse_compatible_source


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
    python_executable: Path | None = None,
) -> dict[str, Any]:
    command_results = _command_results(
        root, project_dir, implementation_plan, run_verification, max_commands, python_executable,
    )
    failed = [item for item in command_results if item.get("status") == "failed"]
    executed = [item for item in command_results if item.get("status") in {"passed", "failed"}]
    executable_acceptance = run_executable_acceptance(
        root=root,
        project_dir=project_dir,
        test_plan=test_plan,
        work_dir=execution_dir,
        python_executable=python_executable,
    )
    if executable_acceptance.get("status") == "failed":
        failed.append({"status": "failed", "command": "executable_acceptance"})
    verified = bool(executed) or executable_acceptance.get("status") == "passed"
    return {
        "artifact_type": "TestResult",
        "role": "programmer_executor",
        "status": "failed" if failed else "ok" if verified else "not_verified",
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
            "verification_status": "failed" if failed else "verified" if verified else "not_verified",
        },
        "executable_acceptance_result": executable_acceptance,
        "source_code_changes": False,
        "registry_changes": False,
        "verification_python": python_executable.resolve().as_posix() if python_executable else None,
    }


def _command_results(
    root: Path,
    project_dir: Path,
    implementation_plan: dict[str, Any],
    run_verification: bool,
    max_commands: int,
    python_executable: Path | None,
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
        results.append(run_command(
            command, _command_cwd(command, root, project_dir), python_executable=python_executable,
        ))
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
    compatibility_modes = {}
    for file_name in files:
        try:
            _, mode = parse_compatible_source(
                (project_dir / file_name).read_text(encoding="utf-8"), file_name
            )
            if mode:
                compatibility_modes[file_name] = mode
        except SyntaxError as exc:
            failures.append(f"{file_name}:{exc.lineno}:{exc.msg}")
    return {
        "command": "project_scoped_syntax_check",
        "kind": "project_scoped_py_compile",
        "scope": files,
        "compatibility_modes": compatibility_modes,
        "status": "failed" if failures else "passed",
        "returncode": 1 if failures else 0,
        "stdout_tail": "",
        "stderr_tail": "\n".join(failures)[-2000:],
    }


def run_command(
    command: str, cwd: Path, *, python_executable: Path | None = None,
) -> dict[str, Any]:
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    argv = command_argv(command)
    if argv is None or not _argv_allowed(argv):
        return {
            "command": command, "status": "failed", "returncode": None,
            "stdout_tail": "", "stderr_tail": "unsafe_or_invalid_command",
        }
    effective_argv = _bind_python(argv, python_executable)
    result = subprocess.run(
        effective_argv,
        cwd=str(cwd),
        shell=False,
        capture_output=True,
        text=True,
        env=env,
        encoding="utf-8",
        errors="replace",
        timeout=180,
    )
    return {
        "command": command,
        "effective_command": subprocess.list2cmdline(effective_argv),
        "status": "passed" if result.returncode == 0 else "failed",
        "returncode": result.returncode,
        "stdout_tail": result.stdout[-2000:],
        "stderr_tail": result.stderr[-2000:],
    }


def _bind_python(command: list[str], python_executable: Path | None) -> list[str]:
    if python_executable is None:
        return command
    return [str(python_executable.resolve()), *command[1:]]


def command_allowed(command: str) -> bool:
    argv = command_argv(command)
    return argv is not None and _argv_allowed(argv)


def _argv_allowed(argv: list[str]) -> bool:
    if not argv or not _python_command(argv[0]):
        return False
    tail = argv[1:]
    if tail[:2] == ["-m", "compileall"]:
        return bool(tail[2:]) and all(_safe_compileall_arg(value) for value in tail[2:])
    if tail[:1] == ["tools/mvp_acceptance.py"]:
        return tail[1:] == ["--skip-pytest"]
    if tail[:2] == ["-m", "pytest"]:
        return _safe_runtime_pytest_args(tail[2:])
    return False


def command_argv(command: str) -> list[str] | None:
    if not command.strip() or any(value in command for value in (";", "&", "|", ">", "<", "\r", "\n")):
        return None
    try:
        values = shlex.split(command, posix=False)
    except ValueError:
        return None
    return [value[1:-1] if len(value) >= 2 and value[0] == value[-1] == '"' else value for value in values]


def _python_command(value: str) -> bool:
    normalized = value.replace("\\", "/").lower()
    return Path(normalized).name in {"python", "python.exe", "python3", "python3.exe"} or normalized == Path(sys.executable).as_posix().lower()


def _safe_compileall_arg(value: str) -> bool:
    if value in {"-b", "-f", "-q", "-qq", "."}:
        return True
    path = value.replace("\\", "/")
    return not value.startswith("-") and not Path(value).is_absolute() and ".." not in path.split("/")


def _safe_runtime_pytest_args(values: list[str]) -> bool:
    targets = [value.replace("\\", "/") for value in values if not value.startswith("-")]
    options = [value for value in values if value.startswith("-")]
    return (
        bool(targets)
        and all(value == "tests/runtime" or value.startswith("tests/runtime/") for value in targets)
        and all(
            value in {"-q", "-x"} or value.startswith("--tb=") or value.startswith("--maxfail=")
            for value in options
        )
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
