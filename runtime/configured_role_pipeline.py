"""Helpers for running configured role pipelines without hard-coded role chains."""

from __future__ import annotations

from typing import Any

from .role_artifact_interpreter import load_role_artifact_pipeline, run_role_artifact_pipeline
from .role_directory import load_role_directory


def run_configured_role_prefix(
    *,
    goal: str,
    project_report: dict[str, Any],
    until_artifact_type: str | None = None,
    until_output_key: str | None = None,
    **kwargs: Any,
) -> dict[str, dict[str, Any]]:
    pipeline = configured_pipeline_prefix(
        until_artifact_type=until_artifact_type,
        until_output_key=until_output_key,
    )
    return run_role_artifact_pipeline(goal=goal, project_report=project_report, pipeline=pipeline, **kwargs)


def configured_pipeline_prefix(
    *,
    until_artifact_type: str | None = None,
    until_output_key: str | None = None,
) -> dict[str, Any]:
    pipeline = load_role_artifact_pipeline()
    if until_artifact_type is None and until_output_key is None:
        return pipeline
    selected = []
    for step in pipeline["steps"]:
        selected.append(step)
        role_id = str(step.get("role_id") or "")
        if until_output_key is not None and step.get("output_key") == until_output_key:
            break
        if until_artifact_type is not None and until_artifact_type in producer_artifact_types(role_id):
            break
    return {**pipeline, "steps": selected}


def artifact_by_type(artifacts: dict[str, dict[str, Any]], artifact_type: str) -> dict[str, Any]:
    for artifact in artifacts.values():
        if artifact.get("artifact_type") == artifact_type:
            return artifact
    raise KeyError(f"pipeline did not produce artifact_type {artifact_type}")


def producer_for_artifact_type(artifact_type: str) -> str:
    roles = dict(load_role_directory().get("roles") or {})
    for role_id, role in roles.items():
        if artifact_type in list(dict(role).get("produces") or []):
            return str(role_id)
    return "unknown"


def producer_artifact_types(role_id: str) -> list[str]:
    roles = dict(load_role_directory().get("roles") or {})
    role = dict(roles.get(role_id) or {})
    return [str(item) for item in list(role.get("produces") or [])]
