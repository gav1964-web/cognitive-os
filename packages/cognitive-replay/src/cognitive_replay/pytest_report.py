"""Collect exact pytest node outcomes in a controlled qualification subprocess."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .process import isolated_environment, run_command
from .evidence import evidence_digest, inside


def run_pytest(
    *, sandbox: Path, python: Path, control: Path, test_entries: list[str],
    phase: str, timeout: int, plugins: list[str],
) -> dict[str, Any]:
    if not test_entries:
        raise ValueError("qualification test targets are required")
    for target in test_entries:
        if target.startswith("-") or not inside(sandbox, target).is_file():
            raise ValueError("qualification test target must be a sandbox file")
    stage = control / phase
    stage.mkdir()
    report_path = stage / "pytest-result.json"
    plugin = stage / "cognitive_os_historical_report.py"
    plugin.write_bytes(Path(__file__).with_name("historical_defect_pytest_plugin.py").read_bytes())
    roots = [str(sandbox)]
    if (sandbox / "src").is_dir():
        roots.insert(0, str(inside(sandbox, "src")))
    roots.append(str(stage))
    bootstrap = stage / "run_tests.py"
    bootstrap.write_text(
        "import sys\nsys.path[:0] = " + repr(roots) + "\nimport pytest\n"
        "raise SystemExit(pytest.main(sys.argv[1:]))\n", encoding="utf-8",
    )
    command = [str(python), "-I", "-B", str(bootstrap), *test_entries,
               "-q", "--tb=short", "--disable-warnings", "-p", "no:cacheprovider",
               "-p", "cognitive_os_historical_report", "-o", "addopts=",
               "--rootdir", str(sandbox), "--basetemp", str(stage / "tmp")]
    for name in plugins:
        command.extend(("-p", name))
    env = isolated_environment(stage / "user-tmp", python)
    env["COGNITIVE_OS_HISTORICAL_REPORT_PATH"] = str(report_path)
    run = run_command(command, cwd=sandbox, env=env, timeout=timeout)
    run["test_targets"] = list(test_entries)
    run["structured"] = read_test_report(report_path, run["returncode"])
    return run


def read_test_report(path: Path, exit_code: int) -> dict[str, Any]:
    try:
        if path.stat().st_size > 5_000_000:
            raise ValueError("oversized pytest report")
        report = json.loads(path.read_text(encoding="utf-8"))
        if report.get("schema_version") != "historical_pytest_result.v1":
            raise ValueError("pytest report schema mismatch")
        if report.get("exit_code") != exit_code:
            raise ValueError("pytest report exit code mismatch")
        collected = report["collected"]
        if len(collected) != len(set(collected)) or len(collected) > 10000:
            raise ValueError("pytest collection must have unique bounded node ids")
        nodes: dict[str, dict[str, Any]] = {node: {} for node in collected}
        for row in report["reports"]:
            node, phase = row["nodeid"], row["phase"]
            if node not in nodes or phase not in {"setup", "call", "teardown"}:
                raise ValueError("pytest result is not bound to collection")
            if phase in nodes[node] or row["outcome"] not in {"passed", "failed", "skipped"}:
                raise ValueError("pytest phase outcome is invalid or repeated")
            nodes[node][phase] = row
        passed, failed, skipped, errors, signatures = [], [], [], [], []
        environment_failure = False
        for node, phases in nodes.items():
            setup, call, teardown = (phases.get(name, {}) for name in ("setup", "call", "teardown"))
            if teardown.get("outcome") != "passed":
                errors.append(node)
            elif setup.get("outcome") == "skipped":
                skipped.append(node)
            elif setup.get("outcome") != "passed":
                errors.append(node)
            elif call.get("outcome") == "failed":
                failed.append(node)
                message = re.sub(r"0x[0-9a-fA-F]+", "0xADDRESS", str(call.get("message") or ""))
                signatures.append([node, message])
                environment_failure |= any(marker in message.lower() for marker in (
                    "modulenotfounderror", "packagenotfounderror",
                ))
            elif call.get("outcome") == "skipped" or call.get("wasxfail"):
                skipped.append(node)
            elif call.get("outcome") == "passed":
                passed.append(node)
            else:
                errors.append(node)
        return {"status": "valid", "collected": sorted(collected), "passed": sorted(passed),
                "failed": sorted(failed), "skipped": sorted(skipped), "errors": sorted(errors),
                "collection_errors": report["collection_errors"],
                "environment_failure": environment_failure,
                "failure_signature": evidence_digest(sorted(signatures)) if failed else None}
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        return {"status": "invalid", "reason": str(exc)[:240]}


def pytest_status(run: dict[str, Any]) -> str:
    if run.get("returncode") == 124:
        return "timeout"
    report = run.get("structured") or {}
    if (report.get("status") != "valid" or report.get("collection_errors") or report.get("errors")
            or report.get("environment_failure")):
        return "environment_blocked"
    if run.get("returncode") == 1 and report.get("failed"):
        return "reproducible_failure"
    if run.get("returncode") == 0 and not report.get("failed"):
        return "passed" if report.get("passed") else "no_tests_executed"
    return "environment_blocked"


def bounded_result(run: dict[str, Any]) -> dict[str, Any]:
    output = f"{run.get('stdout', '')}\n{run.get('stderr', '')}".strip()
    return {"status": pytest_status(run), "returncode": run.get("returncode"),
            "test_targets": run.get("test_targets", []), "output_tail": output[-6000:],
            "structured": run.get("structured")}
