from __future__ import annotations

from pathlib import Path

from runtime.executable_acceptance import run_executable_acceptance


def _literal_plan(target: str, expected: str) -> dict[str, dict[str, list[dict[str, object]]]]:
    return {
        "executable_acceptance": {
            "obligations": [
                {
                    "id": "OBL-001",
                    "acceptance_id": "AC-001",
                    "target": target,
                    "kind": "positive_contract_case",
                    "given": {"value": " Sample "},
                    "expect": {"return_value": expected},
                    "oracle": "output_schema_and_acceptance_criterion",
                },
                {
                    "id": "OBL-002",
                    "acceptance_id": "side_effect_boundary",
                    "target": target,
                    "kind": "side_effect_scope_case",
                    "given": {},
                    "expect": {"no_writes_outside_declared_scope": True},
                    "oracle": "changed_file_list_is_subset_of_writable_scope",
                },
            ]
        }
    }


def test_executable_acceptance_checks_literal_return_value(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "main.py").write_text("def normalize(value):\n    return value.strip().lower()\n", encoding="utf-8")

    result = run_executable_acceptance(
        root=tmp_path,
        project_dir=project,
        test_plan=_literal_plan("main.py:normalize", "sample"),
        work_dir=tmp_path / "work",
    )

    assert result["status"] == "passed"
    assert result["summary"]["signal_strength"] == "executable_callable"


def test_executable_acceptance_marks_wrong_literal_return_as_skipped_sample(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "main.py").write_text("def normalize(value):\n    return value\n", encoding="utf-8")

    result = run_executable_acceptance(
        root=tmp_path,
        project_dir=project,
        test_plan=_literal_plan("main.py:normalize", "sample"),
        work_dir=tmp_path / "work",
    )

    assert result["status"] == "passed"
    assert result["summary"]["signal_strength"] == "meta_only"
    assert result["summary"]["skipped_reason_counts"] == {"positive_sample_execution_failed": 1}
