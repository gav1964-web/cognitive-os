from __future__ import annotations

import json

import pytest

from runtime.role_directory import RoleDirectoryError, load_role_directory
from runtime.config_doctor import _check_role_directory
from runtime.role_workflow_handler_registry import workflow_handler_registry
from runtime.role_workflow_interpreter import (
    RoleWorkflowInterpreterError,
    ordered_workflow_stages,
    run_configured_workflow,
)


def _directory(stages):
    return {"workflow": {"stages": stages}}


def test_workflow_stages_are_ordered_by_dependencies():
    directory = _directory(
        [
            {"stage_id": "review", "depends_on": ["build"]},
            {"stage_id": "build", "depends_on": []},
            {"stage_id": "report", "depends_on": ["review"]},
        ]
    )

    ordered = ordered_workflow_stages(directory=directory)

    assert [stage["stage_id"] for stage in ordered] == ["build", "review", "report"]


def test_workflow_cycle_is_rejected():
    directory = _directory(
        [
            {"stage_id": "build", "depends_on": ["review"]},
            {"stage_id": "review", "depends_on": ["build"]},
        ]
    )

    with pytest.raises(RoleWorkflowInterpreterError, match="dependency cycle"):
        ordered_workflow_stages(directory=directory)


def test_workflow_requires_handler_for_every_stage():
    directory = _directory(
        [
            {"stage_id": "build", "depends_on": []},
            {"stage_id": "review", "depends_on": ["build"]},
        ]
    )
    calls = []

    with pytest.raises(RoleWorkflowInterpreterError, match="no runtime handler: review"):
        run_configured_workflow(state={}, handlers={"build": lambda state: calls.append("build")}, directory=directory)

    assert calls == []


def test_workflow_checks_stage_input_before_handler_runs():
    directory = _directory(
        [{"stage_id": "build", "depends_on": [], "requires": ["project_report"], "provides": ["artifacts"]}]
    )
    calls = []

    with pytest.raises(RoleWorkflowInterpreterError, match="build missing input: project_report"):
        run_configured_workflow(
            state={},
            handlers={"build": lambda state: calls.append("build")},
            directory=directory,
        )

    assert calls == []


def test_workflow_checks_stage_output_after_handler_runs():
    directory = _directory(
        [{"stage_id": "build", "depends_on": [], "requires": [], "provides": ["artifacts"]}]
    )

    with pytest.raises(RoleWorkflowInterpreterError, match="build missing output: artifacts"):
        run_configured_workflow(state={}, handlers={"build": lambda state: None}, directory=directory)


def test_role_directory_rejects_invalid_stage_contract(tmp_path):
    directory = json.loads(json.dumps(load_role_directory()))
    directory["workflow"]["stages"][0]["provides"] = "project_report"
    directory_path = tmp_path / "role_directory.json"
    directory_path.write_text(json.dumps(directory), encoding="utf-8")

    with pytest.raises(RoleDirectoryError, match="provides must be a string list: analyze"):
        load_role_directory(str(directory_path))


def test_default_workflow_handlers_are_registered():
    directory = load_role_directory()
    registry = workflow_handler_registry()

    assert all(stage["handler_id"] in registry for stage in directory["workflow"]["stages"])
    assert all(callable(handler) for handler in registry.values())
    assert all(handler.__module__ == "runtime.role_pipeline_stages" for handler in registry.values())
    assert all(handler.__name__.startswith("stage_") for handler in registry.values())


def test_config_doctor_rejects_unknown_workflow_handler():
    directory = json.loads(json.dumps(load_role_directory()))
    directory["workflow"]["stages"][0]["handler_id"] = "missing.analyze"

    check = _check_role_directory({"role_directory": directory}).to_dict()

    assert check["status"] == "failed"
    assert check["errors"] == ["unknown_workflow_handler:analyze:missing.analyze"]
