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

    assert outputs["executor"] == {"status": "skipped", "reason": "run_executor flag is false"}
    assert context["executor"] == outputs["executor"]


def test_lifecycle_phase_without_configured_hooks_is_empty():
    assert run_lifecycle_phase("before_build", context={}) == {}


def test_role_directory_rejects_hook_binding_to_unknown_artifact_type(tmp_path: Path):
    directory = json.loads(json.dumps(load_role_directory()))
    directory["lifecycle_hooks"][0]["bindings"]["technical_spec"] = "$artifact_type:UnknownSpec"
    directory_path = tmp_path / "role_directory.json"
    directory_path.write_text(json.dumps(directory), encoding="utf-8")

    with pytest.raises(RoleDirectoryError, match="unknown artifact type: UnknownSpec"):
        load_role_directory(str(directory_path))
