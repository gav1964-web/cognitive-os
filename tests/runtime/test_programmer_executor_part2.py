from __future__ import annotations

from tests.runtime.programmer_executor_helpers import *

def test_executable_acceptance_fails_when_callable_accepts_malformed_input(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "main.py").write_text("def loose(**kwargs):\n    return 'ok'\n", encoding="utf-8")
    result = run_executable_acceptance(
        root=tmp_path,
        project_dir=project,
        test_plan={
            "executable_acceptance": {
                "status": "ready",
                "obligations": [
                    {
                        "id": "OBL-001",
                        "acceptance_id": "AC-001",
                        "target": "main.py:loose",
                        "kind": "positive_contract_case",
                        "given": {"text": "sample"},
                        "expect": {"result": "string"},
                        "oracle": "output_schema_and_acceptance_criterion",
                    },
                    {
                        "id": "OBL-002",
                        "acceptance_id": "contract_negative_missing_input",
                        "target": "main.py:loose",
                        "kind": "malformed_input_case",
                        "given": {},
                        "expect": {"error": "controlled_validation_error"},
                        "oracle": "missing_required_input_rejected",
                    },
                    {
                        "id": "OBL-003",
                        "acceptance_id": "side_effect_boundary",
                        "target": "main.py:loose",
                        "kind": "side_effect_scope_case",
                        "given": {"declared_scope": "writable_scope_only"},
                        "expect": {"no_writes_outside_declared_scope": True},
                        "oracle": "changed_file_list_is_subset_of_writable_scope",
                    },
                ],
            }
        },
        work_dir=tmp_path / "work",
    )

    assert result["status"] == "failed"
