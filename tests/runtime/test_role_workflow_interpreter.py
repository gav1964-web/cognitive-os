from __future__ import annotations

import pytest

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
