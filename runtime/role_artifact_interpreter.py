"""Interpret external role artifact pipeline definitions."""

from __future__ import annotations

import importlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
ROLE_ARTIFACT_PIPELINE_PATH = ROOT / "config" / "role_artifact_pipeline.json"


class RoleArtifactInterpreterError(RuntimeError):
    """Raised when a role artifact pipeline cannot be interpreted."""


@lru_cache(maxsize=1)
def load_role_artifact_pipeline(path: str | None = None) -> dict[str, Any]:
    source = Path(path) if path else ROLE_ARTIFACT_PIPELINE_PATH
    payload = json.loads(source.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "role_artifact_pipeline.v1":
        raise RoleArtifactInterpreterError("role artifact pipeline must use schema_version role_artifact_pipeline.v1")
    steps = payload.get("steps")
    if not isinstance(steps, list) or not steps:
        raise RoleArtifactInterpreterError("role artifact pipeline must contain non-empty steps list")
    for step in steps:
        if not isinstance(step, dict):
            raise RoleArtifactInterpreterError("role artifact pipeline step must be an object")
        for field in ("step_id", "role_id", "builder", "output_key", "bindings"):
            if field not in step:
                raise RoleArtifactInterpreterError(f"role artifact pipeline step requires {field}")
        if not isinstance(step.get("bindings"), dict):
            raise RoleArtifactInterpreterError(f"bindings must be an object for step {step.get('step_id')}")
    return payload


def run_role_artifact_pipeline(
    *,
    goal: str,
    project_report: dict[str, Any],
    initial_artifacts: dict[str, dict[str, Any]] | None = None,
    architect_advisory_config: Any = None,
    test_result: dict[str, Any] | None = None,
    executable_acceptance_result: dict[str, Any] | None = None,
    pipeline: dict[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    """Run configured artifact builders with declarative bindings."""

    payload = pipeline or load_role_artifact_pipeline()
    context: dict[str, Any] = {
        "goal": goal,
        "project_report": project_report,
        "architect_advisory_config": architect_advisory_config,
        "test_result": test_result,
        "executable_acceptance_result": executable_acceptance_result,
        "artifacts": dict(initial_artifacts or {}),
    }
    for step in payload["steps"]:
        builder = _load_callable(str(step["builder"]))
        kwargs = {
            str(name): _resolve_binding(value, context)
            for name, value in dict(step.get("bindings", {})).items()
        }
        artifact = builder(**kwargs)
        if not isinstance(artifact, dict):
            raise RoleArtifactInterpreterError(f"builder returned non-object artifact: {step['builder']}")
        expected_role = str(step.get("role_id") or "")
        if expected_role and artifact.get("role") != expected_role:
            raise RoleArtifactInterpreterError(
                f"builder {step['builder']} returned role {artifact.get('role')} instead of {expected_role}"
            )
        context["artifacts"][str(step["output_key"])] = artifact
    return dict(context["artifacts"])


def _resolve_binding(value: Any, context: dict[str, Any]) -> Any:
    if not isinstance(value, str) or not value.startswith("$"):
        return value
    path = value[1:].split(".")
    current: Any = context
    for part in path:
        if isinstance(current, dict):
            current = current.get(part)
        else:
            current = getattr(current, part, None)
        if current is None:
            return None
    return current


def _load_callable(spec: str) -> Callable[..., Any]:
    if ":" not in spec:
        raise RoleArtifactInterpreterError(f"builder must be module:function: {spec}")
    module_name, function_name = spec.split(":", 1)
    module = importlib.import_module(module_name)
    function = getattr(module, function_name, None)
    if not callable(function):
        raise RoleArtifactInterpreterError(f"builder is not callable: {spec}")
    return function
