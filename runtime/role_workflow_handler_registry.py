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
class WorkflowHandlerSpec:
    handler_id: str
    function: Callable[[dict[str, Any]], None]
    requires: tuple[str, ...]
    provides: tuple[str, ...]


def workflow_handler_registry() -> dict[str, WorkflowHandlerSpec]:
    specs = [
        _spec("analyze", stage_analyze, ("root", "project_dir"), ("project_report",)),
        _spec(
            "build",
            stage_build,
            ("goal", "project_report", "architect_advisory_config"),
            ("artifacts", "adr", "spec", "implementation", "test_plan", "lifecycle_context"),
        ),
        _spec("after_build", stage_after_build, ("lifecycle_context",), ("executor", "test_result")),
        _spec(
            "review",
            stage_review,
            ("goal", "project_report", "artifacts", "architect_advisory_config", "test_result"),
            ("artifacts", "review"),
        ),
        _spec(
            "after_review",
            stage_after_review,
            ("lifecycle_context", "artifacts", "adr", "review"),
            ("control_plane", "role_gates", "paths", "human_documents", "next_action"),
        ),
        _spec(
            "after_decision",
            stage_after_decision,
            ("lifecycle_context", "next_action", "run_transform", "force_transform"),
            ("transform",),
        ),
        _spec(
            "assemble_result",
            stage_assemble_result,
            (
                "project_dir", "goal", "adr", "spec", "implementation", "test_plan", "review", "control_plane",
                "role_gates", "transform", "executor", "artifacts", "paths", "human_documents", "next_action",
            ),
            ("result",),
        ),
        _spec("after_result", stage_after_result, ("lifecycle_context", "result"), ("result",)),
    ]
    return {spec.handler_id: spec for spec in specs}


def workflow_handler_contract_errors(stages: list[dict[str, Any]]) -> list[str]:
    registry = workflow_handler_registry()
    errors = []
    for stage in stages:
        stage_id = str(stage.get("stage_id") or "")
        handler_id = str(stage.get("handler_id") or "")
        spec = registry.get(handler_id)
        if spec is None or not callable(spec.function):
            errors.append(f"unknown_workflow_handler:{stage_id}:{handler_id}")
            continue
        if tuple(stage.get("requires") or []) != spec.requires:
            errors.append(f"workflow_handler_requires_mismatch:{stage_id}:{handler_id}")
        if tuple(stage.get("provides") or []) != spec.provides:
            errors.append(f"workflow_handler_provides_mismatch:{stage_id}:{handler_id}")
    return errors


def _spec(
    name: str,
    function: Callable[[dict[str, Any]], None],
    requires: tuple[str, ...],
    provides: tuple[str, ...],
) -> WorkflowHandlerSpec:
    return WorkflowHandlerSpec(f"role_pipeline.{name}", function, requires, provides)
