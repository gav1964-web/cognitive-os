"""Generate and run executable acceptance scaffolds from Tester obligations."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def run_executable_acceptance(
    *,
    root: Path,
    project_dir: Path,
    test_plan: dict[str, Any],
    work_dir: Path,
) -> dict[str, Any]:
    executable = dict(test_plan.get("executable_acceptance", {}))
    obligations = [dict(item) for item in executable.get("obligations", []) if isinstance(item, dict)]
    scaffold_dir = work_dir / "executable_acceptance"
    scaffold_dir.mkdir(parents=True, exist_ok=True)
    obligations_path = scaffold_dir / "obligations.json"
    tests_dir = scaffold_dir / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    test_path = tests_dir / "test_acceptance_generated.py"
    obligations_path.write_text(json.dumps(obligations, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    test_path.write_text(_pytest_source(obligations_path), encoding="utf-8")
    command = [sys.executable, "-m", "pytest", str(tests_dir), "-q"]
    command_result = _run_command(command, cwd=scaffold_dir)
    passed = command_result["returncode"] == 0
    result = {
        "artifact_type": "ExecutableAcceptanceResult",
        "status": "passed" if passed else "failed",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "project": project_dir.as_posix(),
        "scaffold_dir": scaffold_dir.as_posix(),
        "obligations_path": obligations_path.as_posix(),
        "generated_tests": [test_path.as_posix()],
        "summary": {
            "obligation_count": len(obligations),
            "acceptance_ids": sorted({str(item.get("acceptance_id")) for item in obligations if item.get("acceptance_id")}),
            "generated_test_count": 1,
            "passed": passed,
        },
        "command": command_result,
        "source_code_changes": False,
        "registry_changes": False,
        "limitations": [
            "v0.2 executes obligation and boundary meta-checks; project-specific function invocation requires a later harness.",
        ],
    }
    result_path = scaffold_dir / "executable_acceptance_result.json"
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    result["result_path"] = result_path.as_posix()
    return result


def _pytest_source(obligations_path: Path) -> str:
    escaped = obligations_path.as_posix()
    return f'''"""Generated executable acceptance scaffold."""

import json
from pathlib import Path


OBLIGATIONS = Path(r"{escaped}")


def _rows():
    return json.loads(OBLIGATIONS.read_text(encoding="utf-8"))


def test_obligations_are_present_and_typed():
    rows = _rows()
    assert rows, "Tester produced no executable acceptance obligations"
    for row in rows:
        assert row.get("id")
        assert row.get("acceptance_id")
        assert row.get("target")
        assert row.get("kind")
        assert row.get("oracle")


def test_positive_contract_cases_have_expected_shape():
    positives = [row for row in _rows() if row.get("kind") == "positive_contract_case"]
    assert positives, "At least one positive contract case is required"
    for row in positives:
        assert isinstance(row.get("given"), dict)
        assert isinstance(row.get("expect"), dict)
        assert row["expect"], "Positive cases must define an expected output shape"


def test_malformed_input_case_is_controlled():
    malformed = [row for row in _rows() if row.get("kind") == "malformed_input_case"]
    assert malformed, "Malformed input obligation is required"
    for row in malformed:
        assert row.get("expect", {{}}).get("error") == "controlled_validation_error"


def test_side_effect_boundary_is_declared():
    boundaries = [row for row in _rows() if row.get("kind") == "side_effect_scope_case"]
    assert boundaries, "Side-effect boundary obligation is required"
    for row in boundaries:
        assert row.get("expect", {{}}).get("no_writes_outside_declared_scope") is True
'''


def _run_command(command: list[str], *, cwd: Path) -> dict[str, Any]:
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    completed = subprocess.run(
        command,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=120,
    )
    return {
        "command": command,
        "returncode": completed.returncode,
        "status": "passed" if completed.returncode == 0 else "failed",
        "stdout_tail": completed.stdout[-2000:],
        "stderr_tail": completed.stderr[-2000:],
    }
