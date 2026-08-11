"""Static registry of runtime handlers available to configured role workflows."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .role_pipeline_stages import (
    stage_after_build,
    stage_after_decision,
    stage_after_result,
    stage_after_review,
    stage_analyze,
    stage_assemble_result,
    stage_build,
    stage_review,
)


@dataclass(frozen=True)
class WorkflowHandlerRegistration:
    function: Callable[[dict[str, Any]], None]
    effects: tuple[str, ...]


def workflow_handler_registry() -> dict[str, WorkflowHandlerRegistration]:
    return {
        "role_pipeline.analyze": WorkflowHandlerRegistration(stage_analyze, ("filesystem_read", "temporary_cwd")),
        "role_pipeline.build": WorkflowHandlerRegistration(stage_build, ("model_inference",)),
        "role_pipeline.after_build": WorkflowHandlerRegistration(stage_after_build, ("delegated_lifecycle",)),
        "role_pipeline.review": WorkflowHandlerRegistration(stage_review, ()),
        "role_pipeline.after_review": WorkflowHandlerRegistration(stage_after_review, ("delegated_lifecycle",)),
        "role_pipeline.after_decision": WorkflowHandlerRegistration(stage_after_decision, ("delegated_lifecycle",)),
        "role_pipeline.assemble_result": WorkflowHandlerRegistration(stage_assemble_result, ()),
        "role_pipeline.after_result": WorkflowHandlerRegistration(stage_after_result, ("delegated_lifecycle",)),
    }


def workflow_handler_registration_errors(stages: list[dict[str, Any]]) -> list[str]:
    registry = workflow_handler_registry()
    errors = []
    for stage in stages:
        stage_id = str(stage.get("stage_id") or "")
        handler_id = str(stage.get("handler_id") or "")
        registration = registry.get(handler_id)
        if registration is None or not callable(registration.function):
            errors.append(f"unknown_workflow_handler:{stage_id}:{handler_id}")
            continue
        if tuple(stage.get("effects") or []) != registration.effects:
            errors.append(f"workflow_handler_effects_mismatch:{stage_id}:{handler_id}")
    return errors


def workflow_handler_functions() -> dict[str, Callable[[dict[str, Any]], None]]:
    return {handler_id: registration.function for handler_id, registration in workflow_handler_registry().items()}
