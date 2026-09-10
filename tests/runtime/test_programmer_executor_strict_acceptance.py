from __future__ import annotations

import json
from pathlib import Path

import pytest

from runtime.programmer_executor import run_programmer_executor


def _plan(target: str) -> dict[str, object]:
    return {
        "implementation_target": {"candidate": target},
        "patch_intent": {"target_symbol": target},
        "writable_scope": [target],
        "expected_files": [target.split(":", 1)[0]],
        "verification_commands": ["python -m compileall ."],
    }


def _test_plan(target: str, given: dict[str, object], expect: dict[str, object]) -> dict[str, object]:
    return {
        "executable_acceptance": {
            "obligations": [
                {
                    "id": "OBL-001",
                    "acceptance_id": "AC-001",
                    "target": target,
                    "kind": "positive_contract_case",
                    "given": given,
                    "expect": expect,
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


def test_executor_synthesizes_comma_split_transform_from_contract(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "main.py").write_text("def parse_items(value):\n    pass\n", encoding="utf-8")

    result = run_programmer_executor(
        root=tmp_path,
        project_dir=project,
        technical_spec={"artifact_type": "TechnicalSpec"},
        implementation_plan=_plan("main.py:parse_items"),
        test_plan=_test_plan("main.py:parse_items", {"value": "one, two,,three"}, {"return_value": ["one", "two", "three"]}),
        run_verification=True,
    )

    patch = json.loads(Path(result["patch_package_path"]).read_text(encoding="utf-8"))
    source = (Path(patch["patch_synthesis"]["sandbox_project"]) / "main.py").read_text(encoding="utf-8")
    assert result["status"] == "ok"
    assert patch["patch_synthesis"]["reason"] == "contract_transform_identity_return_synthesized"
    assert patch["patches"][0]["transform"] == "comma_split_strip_nonempty"
    assert patch["patches"][0]["transform_evidence"]["body_kind"] == "pass_stub"
    assert "[part.strip() for part in value.split(',') if part.strip()]" in source


def test_executor_synthesizes_sum_transform_from_contract(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "main.py").write_text("def total(values):\n    return values\n", encoding="utf-8")

    result = run_programmer_executor(
        root=tmp_path,
        project_dir=project,
        technical_spec={"artifact_type": "TechnicalSpec"},
        implementation_plan=_plan("main.py:total"),
        test_plan=_test_plan("main.py:total", {"values": [1, 2, 3]}, {"return_value": 6}),
        run_verification=True,
    )

    patch = json.loads(Path(result["patch_package_path"]).read_text(encoding="utf-8"))
    source = (Path(patch["patch_synthesis"]["sandbox_project"]) / "main.py").read_text(encoding="utf-8")
    assert result["status"] == "ok"
    assert patch["patch_synthesis"]["reason"] == "contract_transform_identity_return_synthesized"
    assert patch["patches"][0]["transform"] == "sum_numbers"
    assert "return sum(values)" in source


@pytest.mark.parametrize(
    ("transform", "sample", "expected", "expression"),
    [
        ("len_sequence", ["a", "b"], 2, "return len(values)"),
        ("first_item", ["a", "b"], "a", "return values[0]"),
        ("last_item", ["a", "b"], "b", "return values[-1]"),
        ("sorted_list", [3, 1, 2], [1, 2, 3], "return sorted(values)"),
        ("unique_preserve_order", ["a", "b", "a"], ["a", "b"], "return list(dict.fromkeys(values))"),
    ],
)
def test_executor_synthesizes_list_shape_transform_from_contract(
    tmp_path: Path,
    transform: str,
    sample: object,
    expected: object,
    expression: str,
):
    project = tmp_path / "project"
    project.mkdir()
    (project / "main.py").write_text("def shape(values):\n    pass\n", encoding="utf-8")

    result = run_programmer_executor(
        root=tmp_path,
        project_dir=project,
        technical_spec={"artifact_type": "TechnicalSpec"},
        implementation_plan=_plan("main.py:shape"),
        test_plan=_test_plan("main.py:shape", {"values": sample}, {"return_value": expected}),
        run_verification=True,
    )

    patch = json.loads(Path(result["patch_package_path"]).read_text(encoding="utf-8"))
    source = (Path(patch["patch_synthesis"]["sandbox_project"]) / "main.py").read_text(encoding="utf-8")
    assert result["status"] == "ok"
    assert patch["patches"][0]["transform"] == transform
    assert expression in source


def test_prepared_patch_fails_when_acceptance_cannot_execute_callable(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "main.py").write_text("def normalize(value):\n    return value\n", encoding="utf-8")

    result = run_programmer_executor(
        root=tmp_path,
        project_dir=project,
        technical_spec={"artifact_type": "TechnicalSpec"},
        implementation_plan=_plan("main.py:normalize"),
        test_plan=_test_plan("main.py:normalize", {"value": {"__fixture__": "missing"}}, {"return_value": "sample"}),
        run_verification=True,
    )

    test_result = json.loads(Path(result["test_result_path"]).read_text(encoding="utf-8"))
    assert result["status"] == "failed"
    assert test_result["summary"]["prepared_patch_acceptance_gate"] == "failed_non_callable_acceptance"
