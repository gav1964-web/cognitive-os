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
    harness = _harness_summary(project_dir, obligations)
    test_path.write_text(_pytest_source(obligations_path, project_dir, harness), encoding="utf-8")
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
            "callable_harness_count": harness["callable_harness_count"],
            "passed": passed,
        },
        "command": command_result,
        "source_code_changes": False,
        "registry_changes": False,
        "limitations": [
            "v0.3 invokes simple file.py:function targets with kwargs; classes, async functions, methods and framework handlers remain meta-checked.",
        ],
    }
    result_path = scaffold_dir / "executable_acceptance_result.json"
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    result["result_path"] = result_path.as_posix()
    return result


def _pytest_source(obligations_path: Path, project_dir: Path, harness: dict[str, Any]) -> str:
    escaped = obligations_path.as_posix()
    project = project_dir.resolve().as_posix()
    harness_payload = json.dumps(harness, ensure_ascii=False, sort_keys=True)
    return f'''"""Generated executable acceptance scaffold."""

import importlib.util
import json
from pathlib import Path


OBLIGATIONS = Path(r"{escaped}")
PROJECT_DIR = Path(r"{project}")
HARNESS = {harness_payload!r}


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


def test_simple_python_targets_execute_positive_contract_cases():
    harness = json.loads(HARNESS)
    if harness.get("callable_harness_count", 0) == 0:
        return
    for row in _rows():
        if row.get("kind") != "positive_contract_case":
            continue
        target = row.get("target", "")
        if target not in harness.get("callable_targets", []):
            continue
        func = _load_function(target)
        result = func(**row.get("given", {{}}))
        _assert_expected_shape(result, row.get("expect", {{}}))


def test_simple_python_targets_reject_missing_required_input():
    harness = json.loads(HARNESS)
    if harness.get("callable_harness_count", 0) == 0:
        return
    for row in _rows():
        if row.get("kind") != "malformed_input_case":
            continue
        target = row.get("target", "")
        if target not in harness.get("callable_targets", []):
            continue
        func = _load_function(target)
        try:
            func(**row.get("given", {{}}))
        except (TypeError, ValueError):
            continue
        raise AssertionError(f"{{target}} accepted malformed input")


def _load_function(target):
    path_text, _, symbol = target.partition(":")
    assert path_text.endswith(".py") and symbol, f"unsupported callable target: {{target}}"
    path = (PROJECT_DIR / path_text).resolve()
    assert PROJECT_DIR.resolve() in path.parents or path == PROJECT_DIR.resolve()
    spec = importlib.util.spec_from_file_location("acceptance_target", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    func = getattr(module, symbol)
    assert callable(func), f"target is not callable: {{target}}"
    return func


def _assert_expected_shape(result, expect):
    if not isinstance(expect, dict) or not expect:
        return
    if set(expect) == {{"result"}}:
        assert result is not None
        return
    assert isinstance(result, dict), "multi-field output contract expects dict result"
    for key in expect:
        assert key in result
'''


def _harness_summary(project_dir: Path, obligations: list[dict[str, Any]]) -> dict[str, Any]:
    targets = []
    skipped = []
    for row in obligations:
        target = str(row.get("target") or "")
        if target in targets or target in skipped:
            continue
        if _callable_target_supported(project_dir, target):
            targets.append(target)
        elif target:
            skipped.append(target)
    return {
        "version": "executable_acceptance_harness_v0.3",
        "callable_harness_count": len(targets),
        "callable_targets": targets,
        "meta_checked_targets": skipped,
    }


def _callable_target_supported(project_dir: Path, target: str) -> bool:
    path_text, separator, symbol = target.partition(":")
    if separator != ":" or not path_text.endswith(".py") or not symbol or "." in symbol:
        return False
    path = (project_dir / path_text).resolve()
    try:
        path.relative_to(project_dir.resolve())
    except ValueError:
        return False
    return path.is_file()


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
