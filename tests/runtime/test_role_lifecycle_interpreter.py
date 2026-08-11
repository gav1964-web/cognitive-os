from __future__ import annotations

import json
from pathlib import Path

import pytest

from runtime.role_directory import RoleDirectoryError, lifecycle_hooks, load_role_directory
from runtime.role_lifecycle_interpreter import run_lifecycle_phase


def test_default_lifecycle_hooks_are_loaded_from_role_directory():
    hooks = lifecycle_hooks()

    assert [hook["hook_id"] for hook in hooks] == [
        "programmer_executor",
        "cognitive_control_plane",
        "role_gates",
        "artifact_writer",
        "human_document_writer",
        "project_transform",
        "pipeline_report_writer",
    ]


def test_after_build_hook_resolves_artifacts_by_contract_type(tmp_path: Path):
    artifacts = {
        "renamed_spec": {"artifact_type": "TechnicalSpec"},
        "renamed_plan": {"artifact_type": "ImplementationPlan"},
        "renamed_tests": {"artifact_type": "TestPlan"},
    }
    context = {
        "root": tmp_path,
        "project_dir": tmp_path / "project",
        "artifacts": artifacts,
        "run_executor": False,
    }

    outputs = run_lifecycle_phase("after_build", context=context)

    assert outputs["executor"]["status"] == "skipped"
    assert outputs["executor"]["reason"] == "side effect permission denied"
    assert context["executor"] == outputs["executor"]


def test_lifecycle_phase_without_configured_hooks_is_empty():
    assert run_lifecycle_phase("before_build", context={}) == {}


def test_side_effect_hook_is_not_loaded_without_permission():
    directory = {
        "lifecycle_hooks": [
            {
                "hook_id": "blocked_writer",
                "phase": "after_review",
                "callable": "missing.module:write",
                "output_key": "blocked_writer",
                "side_effects": ["filesystem_write"],
                "permission": "$write",
                "bindings": {},
            }
        ]
    }

    outputs = run_lifecycle_phase("after_review", context={"write": False}, directory=directory)

    assert outputs["blocked_writer"]["status"] == "skipped"
    assert outputs["blocked_writer"]["side_effects"] == ["filesystem_write"]


def test_role_directory_rejects_hook_binding_to_unknown_artifact_type(tmp_path: Path):
    directory = json.loads(json.dumps(load_role_directory()))
    directory["lifecycle_hooks"][0]["bindings"]["technical_spec"] = "$artifact_type:UnknownSpec"
    directory_path = tmp_path / "role_directory.json"
    directory_path.write_text(json.dumps(directory), encoding="utf-8")

    with pytest.raises(RoleDirectoryError, match="unknown artifact type: UnknownSpec"):
        load_role_directory(str(directory_path))


def test_role_directory_rejects_side_effect_hook_without_permission(tmp_path: Path):
    directory = json.loads(json.dumps(load_role_directory()))
    directory["lifecycle_hooks"][0].pop("permission")
    directory_path = tmp_path / "role_directory.json"
    directory_path.write_text(json.dumps(directory), encoding="utf-8")

    with pytest.raises(RoleDirectoryError, match="requires permission binding: programmer_executor"):
        load_role_directory(str(directory_path))
