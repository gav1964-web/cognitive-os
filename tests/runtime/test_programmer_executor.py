from __future__ import annotations

import json
from pathlib import Path

from runtime.executable_acceptance import run_executable_acceptance
from runtime.programmer_executor import run_programmer_executor


def test_programmer_executor_writes_patch_package_and_test_result(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "main.py").write_text("def normalize_text(text: str) -> str:\n    return text.strip().lower()\n", encoding="utf-8")
    spec = {"artifact_type": "TechnicalSpec", "role": "spec_writer"}
    plan = {
        "artifact_type": "ImplementationPlan",
        "role": "implementer",
        "implementation_target": {"candidate": "main.py:normalize_text"},
        "writable_scope": ["main.py:normalize_text"],
        "expected_files": ["main.py"],
        "verification_commands": ["python -m compileall ."],
    }
    test_plan = {
        "artifact_type": "TestPlan",
        "role": "tester",
        "executable_acceptance": {
            "status": "ready",
            "obligations": [
                {
                    "id": "OBL-001",
                    "acceptance_id": "AC-001",
                    "target": "main.py:normalize_text",
                    "kind": "positive_contract_case",
                    "given": {"text": " Sample "},
                    "expect": {"result": "string"},
                    "oracle": "output_schema_and_acceptance_criterion",
                },
                {
                    "id": "OBL-002",
                    "acceptance_id": "contract_negative_missing_input",
                    "target": "main.py:normalize_text",
                    "kind": "malformed_input_case",
                    "given": {},
                    "expect": {"error": "controlled_validation_error"},
                    "oracle": "missing_required_input_rejected",
                },
                {
                    "id": "OBL-003",
                    "acceptance_id": "side_effect_boundary",
                    "target": "main.py:normalize_text",
                    "kind": "side_effect_scope_case",
                    "given": {"declared_scope": "writable_scope_only"},
                    "expect": {"no_writes_outside_declared_scope": True},
                    "oracle": "changed_file_list_is_subset_of_writable_scope",
                },
            ],
        },
    }

    result = run_programmer_executor(
        root=tmp_path,
        project_dir=project,
        technical_spec=spec,
        implementation_plan=plan,
        test_plan=test_plan,
        run_verification=True,
    )

    assert result["status"] == "ok"
    assert result["source_code_changes"] is False
    patch = json.loads(Path(result["patch_package_path"]).read_text(encoding="utf-8"))
    test_result = json.loads(Path(result["test_result_path"]).read_text(encoding="utf-8"))
    assert patch["artifact_type"] == "PatchPackage"
    assert patch["snapshot"][0]["status"] == "copied"
    assert test_result["artifact_type"] == "TestResult"
    assert test_result["summary"]["passed"] == 1
    assert test_result["executable_acceptance_result"]["status"] == "passed"
    assert Path(test_result["executable_acceptance_result"]["generated_tests"][0]).is_file()


def test_programmer_executor_blocks_source_apply_in_mvp(tmp_path: Path):
    result = run_programmer_executor(
        root=tmp_path,
        project_dir=tmp_path,
        technical_spec={},
        implementation_plan={"implementation_target": {"candidate": "main.py:normalize_text"}},
        test_plan={},
        apply_source=True,
    )

    assert result["status"] == "blocked"
    assert result["reason"] == "source_edit_apply_not_enabled_in_mvp"


def test_executable_acceptance_runner_fails_empty_obligations(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    result = run_executable_acceptance(
        root=tmp_path,
        project_dir=project,
        test_plan={"executable_acceptance": {"status": "empty", "obligations": []}},
        work_dir=tmp_path / "work",
    )

    assert result["artifact_type"] == "ExecutableAcceptanceResult"
    assert result["status"] == "failed"
