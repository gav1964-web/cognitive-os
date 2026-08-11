"""Static registry of runtime handlers available to configured role workflows."""

from __future__ import annotations

from collections.abc import Callable
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


def workflow_handler_registry() -> dict[str, Callable[[dict[str, Any]], None]]:
    return {
        "role_pipeline.analyze": stage_analyze,
        "role_pipeline.build": stage_build,
        "role_pipeline.after_build": stage_after_build,
        "role_pipeline.review": stage_review,
        "role_pipeline.after_review": stage_after_review,
        "role_pipeline.after_decision": stage_after_decision,
        "role_pipeline.assemble_result": stage_assemble_result,
        "role_pipeline.after_result": stage_after_result,
    }


def workflow_handler_registration_errors(stages: list[dict[str, Any]]) -> list[str]:
    registry = workflow_handler_registry()
    errors = []
    for stage in stages:
        stage_id = str(stage.get("stage_id") or "")
        handler_id = str(stage.get("handler_id") or "")
        if not callable(registry.get(handler_id)):
            errors.append(f"unknown_workflow_handler:{stage_id}:{handler_id}")
    return errors
