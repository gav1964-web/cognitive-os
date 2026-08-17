"""Helpers for running configured role pipelines without hard-coded role chains."""

from __future__ import annotations

from typing import Any

from .role_artifact_interpreter import load_role_artifact_pipeline, run_role_artifact_pipeline
from .role_directory import load_role_directory
from .technical_spec_policy import load_technical_spec_policy


def run_configured_role_prefix(
    *,
    goal: str,
    project_report: dict[str, Any],
    until_artifact_type: str | None = None,
    until_output_key: str | None = None,
    reselection_triggers: set[str] | None = None,
    **kwargs: Any,
) -> dict[str, dict[str, Any]]:
    pipeline = configured_pipeline_prefix(
        until_artifact_type=until_artifact_type,
        until_output_key=until_output_key,
    )
    artifacts = run_role_artifact_pipeline(goal=goal, project_report=project_report, pipeline=pipeline, **kwargs)
    if not _pipeline_produces(pipeline, "TechnicalSpec"):
        return artifacts
    return _close_first_slice_reselection_loop(
        artifacts=artifacts,
        goal=goal,
        project_report=project_report,
        pipeline=pipeline,
        pipeline_kwargs=kwargs,
        reselection_triggers=reselection_triggers,
    )


def _close_first_slice_reselection_loop(
    *,
    artifacts: dict[str, dict[str, Any]],
    goal: str,
    project_report: dict[str, Any],
    pipeline: dict[str, Any],
    pipeline_kwargs: dict[str, Any],
    reselection_triggers: set[str] | None = None,
) -> dict[str, dict[str, Any]]:
    from .architect_first_slice_reselection import reselect_architecture_first_slice

    policy = dict(load_technical_spec_policy().get("first_slice_reselection") or {})
    if not policy.get("enabled", True):
        return artifacts
    initial_request = dict(artifact_by_type(artifacts, "TechnicalSpec").get("first_slice_reselection_request") or {})
    if reselection_triggers is not None and str(initial_request.get("trigger") or "") not in reselection_triggers:
        return artifacts
    maximum = max(0, int(policy.get("max_iterations") or 0))
    user_transform = pipeline_kwargs.get("artifact_transform")
    current = artifacts
    for iteration in range(1, maximum + 1):
        adr = artifact_by_type(current, "ArchitectureDecisionRecord")
        spec = artifact_by_type(current, "TechnicalSpec")
        resolution = reselect_architecture_first_slice(
            architecture_decision=adr,
            technical_spec=spec,
            project_report=project_report,
            iteration=iteration,
        )
        revised = dict(resolution.get("architecture_decision") or adr)
        if resolution.get("status") != "selected":
            current[_artifact_key(current, "ArchitectureDecisionRecord")] = revised
            _attach_reselection_resolution(spec, resolution, terminal=True)
            _propagate_reselection_request(current, spec)
            return current
        rerun_kwargs = dict(pipeline_kwargs)
        rerun_kwargs["artifact_transform"] = _replacement_transform(revised, user_transform)
        current = run_role_artifact_pipeline(
            goal=goal,
            project_report=project_report,
            pipeline=pipeline,
            **rerun_kwargs,
        )
        rerun_spec = artifact_by_type(current, "TechnicalSpec")
        _attach_reselection_resolution(rerun_spec, resolution, terminal=False)
        _propagate_reselection_request(current, rerun_spec)
        if dict(rerun_spec.get("first_slice_reselection_request") or {}).get("status") != "required":
            return current
    spec = artifact_by_type(current, "TechnicalSpec")
    _attach_reselection_resolution(spec, {"status": "iteration_limit"}, terminal=True)
    _propagate_reselection_request(current, spec)
    return current


def _replacement_transform(revised_adr: dict[str, Any], user_transform: Any) -> Any:
    def transform(artifact: dict[str, Any]) -> dict[str, Any]:
        transformed = user_transform(artifact) if callable(user_transform) else artifact
        if transformed.get("artifact_type") == "ArchitectureDecisionRecord":
            return revised_adr
        return transformed

    return transform


def _attach_reselection_resolution(
    spec: dict[str, Any], resolution: dict[str, Any], *, terminal: bool
) -> None:
    request = dict(spec.get("first_slice_reselection_request") or {})
    request["resolution_status"] = resolution.get("status")
    request["terminal"] = terminal
    if resolution.get("outcome"):
        request["outcome"] = resolution["outcome"]
    spec["first_slice_reselection_request"] = request


def _propagate_reselection_request(
    artifacts: dict[str, dict[str, Any]], technical_spec: dict[str, Any]
) -> None:
    request = dict(technical_spec.get("first_slice_reselection_request") or {})
    for artifact in artifacts.values():
        if "first_slice_reselection_request" in artifact:
            artifact["first_slice_reselection_request"] = dict(request)


def _artifact_key(artifacts: dict[str, dict[str, Any]], artifact_type: str) -> str:
    return next(key for key, artifact in artifacts.items() if artifact.get("artifact_type") == artifact_type)


def _pipeline_produces(pipeline: dict[str, Any], artifact_type: str) -> bool:
    return any(artifact_type in producer_artifact_types(str(step.get("role_id") or "")) for step in pipeline["steps"])


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


def configured_pipeline_phase(phase: str) -> dict[str, Any]:
    pipeline = load_role_artifact_pipeline()
    selected = [step for step in pipeline["steps"] if str(step.get("phase") or "build") == phase]
    if not selected:
        raise ValueError(f"configured role pipeline has no phase: {phase}")
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
