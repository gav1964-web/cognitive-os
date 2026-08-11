"""Run the configured role workflow in dependency order."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .role_directory import workflow_initial_state, workflow_stages
from .role_workflow_contracts import workflow_dataflow_errors


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
    handlers: dict[str, Callable[[dict[str, Any]], None]] | None = None,
    directory: dict[str, Any] | None = None,
) -> None:
    stages = ordered_workflow_stages(directory=directory)
    initial_state = workflow_initial_state(directory=directory) or list(state)
    dataflow_errors = workflow_dataflow_errors(stages, initial_state)
    if dataflow_errors:
        raise RoleWorkflowInterpreterError(dataflow_errors[0])
    if handlers is None:
        from .role_workflow_handler_registry import workflow_handler_registration_errors, workflow_handler_registry

        registration_errors = workflow_handler_registration_errors(stages)
        if registration_errors:
            raise RoleWorkflowInterpreterError(registration_errors[0])
        handlers = workflow_handler_registry()
    handler_keys = [str(stage.get("handler_id") or stage["stage_id"]) for stage in stages]
    missing = [str(stage["stage_id"]) for stage, key in zip(stages, handler_keys) if key not in handlers]
    if missing:
        raise RoleWorkflowInterpreterError(f"role workflow has no runtime handler: {missing[0]}")
    for stage, handler_key in zip(stages, handler_keys):
        stage_id = str(stage["stage_id"])
        _require_state(stage_id, "input", list(stage.get("requires") or []), state)
        handlers[handler_key](state)
        _require_state(stage_id, "output", list(stage.get("provides") or []), state)


def _require_state(stage_id: str, boundary: str, paths: list[str], state: dict[str, Any]) -> None:
    missing = [path for path in paths if not _state_path_exists(state, path)]
    if missing:
        raise RoleWorkflowInterpreterError(f"role workflow {stage_id} missing {boundary}: {missing[0]}")


def _state_path_exists(state: dict[str, Any], path: str) -> bool:
    current: Any = state
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return False
        current = current[part]
    return True
