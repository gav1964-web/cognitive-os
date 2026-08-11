"""Run the configured role workflow in dependency order."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .role_directory import workflow_stages


class RoleWorkflowInterpreterError(RuntimeError):
    """Raised when the configured workflow cannot be executed."""


def ordered_workflow_stages(*, directory: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    pending = workflow_stages(directory=directory)
    ordered = []
    completed: set[str] = set()
    while pending:
        ready = [stage for stage in pending if set(stage.get("depends_on") or []) <= completed]
        if not ready:
            blocked = ",".join(str(stage.get("stage_id") or "") for stage in pending)
            raise RoleWorkflowInterpreterError(f"role workflow contains a dependency cycle: {blocked}")
        for stage in ready:
            pending.remove(stage)
            ordered.append(stage)
            completed.add(str(stage["stage_id"]))
    return ordered


def run_configured_workflow(
    *,
    state: dict[str, Any],
    handlers: dict[str, Callable[[dict[str, Any]], None]],
    directory: dict[str, Any] | None = None,
) -> None:
    stages = ordered_workflow_stages(directory=directory)
    missing = [str(stage["stage_id"]) for stage in stages if str(stage["stage_id"]) not in handlers]
    if missing:
        raise RoleWorkflowInterpreterError(f"role workflow has no runtime handler: {missing[0]}")
    for stage in stages:
        stage_id = str(stage["stage_id"])
        handlers[stage_id](state)
