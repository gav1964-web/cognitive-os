"""Load the external role directory used by role interpreters."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ROLE_DIRECTORY_PATH = ROOT / "config" / "role_directory.json"


class RoleDirectoryError(RuntimeError):
    """Raised when the external role directory is invalid."""


@lru_cache(maxsize=1)
def load_role_directory(path: str | None = None) -> dict[str, Any]:
    source = Path(path) if path else ROLE_DIRECTORY_PATH
    payload = json.loads(source.read_text(encoding="utf-8"))
    if payload.get("schema_version") not in {"role_directory.v1", "role_directory.v2"}:
        raise RoleDirectoryError("role directory must use schema_version role_directory.v1 or role_directory.v2")
    if payload.get("status") != "active":
        raise RoleDirectoryError("role directory must be active")
    _validate_workflow(payload)
    roles = payload.get("roles")
    if not isinstance(roles, dict) or not roles:
        raise RoleDirectoryError("role directory must contain non-empty roles object")
    for role_id, role in roles.items():
        if not isinstance(role, dict):
            raise RoleDirectoryError(f"role entry must be object: {role_id}")
        if not role.get("label") or not role.get("description"):
            raise RoleDirectoryError(f"role entry requires label and description: {role_id}")
        if not isinstance(role.get("capabilities"), list):
            raise RoleDirectoryError(f"role entry requires capabilities list: {role_id}")
        if not isinstance(role.get("consumes"), list) or not isinstance(role.get("produces"), list):
            raise RoleDirectoryError(f"role entry requires consumes/produces lists: {role_id}")
        if payload.get("schema_version") == "role_directory.v2":
            _validate_v2_role(role_id, role)
    pipeline = payload.get("pipeline")
    if not isinstance(pipeline, list):
        raise RoleDirectoryError("role directory must contain pipeline list")
    for step in pipeline:
        if not isinstance(step, dict):
            raise RoleDirectoryError("role directory pipeline step must be object")
        role_id = str(step.get("role_id") or "")
        if role_id not in roles:
            raise RoleDirectoryError(f"pipeline step references unknown role: {role_id}")
        if "artifact_builder" not in roles[role_id]:
            raise RoleDirectoryError(f"pipeline role has no artifact_builder: {role_id}")
        for field in ("step_id", "role_id", "output_key", "bindings"):
            if field not in step:
                raise RoleDirectoryError(f"pipeline step requires {field}")
        phase = str(step.get("phase") or "")
        if payload.get("schema_version") == "role_directory.v2" and phase not in {"build", "review"}:
            raise RoleDirectoryError(f"pipeline step requires build or review phase: {step.get('step_id')}")
    hooks = payload.get("lifecycle_hooks", [])
    if not isinstance(hooks, list):
        raise RoleDirectoryError("role directory lifecycle_hooks must be a list")
    seen_hooks = set()
    seen_hook_outputs = set()
    produced_types = {
        str(artifact_type)
        for role in roles.values()
        for artifact_type in list(dict(role).get("produces") or [])
    }
    for hook in hooks:
        if not isinstance(hook, dict):
            raise RoleDirectoryError("role lifecycle hook must be an object")
        for field in ("hook_id", "phase", "callable", "output_key", "bindings"):
            if field not in hook:
                raise RoleDirectoryError(f"role lifecycle hook requires {field}")
        hook_id = str(hook["hook_id"])
        if not hook_id or hook_id in seen_hooks:
            raise RoleDirectoryError(f"role lifecycle hook_id must be unique: {hook_id}")
        seen_hooks.add(hook_id)
        output_key = str(hook["output_key"])
        if not output_key or output_key in seen_hook_outputs:
            raise RoleDirectoryError(f"role lifecycle output_key must be unique: {output_key}")
        seen_hook_outputs.add(output_key)
        if hook["phase"] not in {"after_build", "after_review", "after_decision", "after_result"}:
            raise RoleDirectoryError(f"unsupported role lifecycle phase: {hook['phase']}")
        if ":" not in str(hook["callable"]):
            raise RoleDirectoryError(f"role lifecycle callable must be module:function: {hook_id}")
        if not isinstance(hook["bindings"], dict):
            raise RoleDirectoryError(f"role lifecycle hook bindings must be an object: {hook_id}")
        side_effects = hook.get("side_effects", [])
        if not isinstance(side_effects, list):
            raise RoleDirectoryError(f"role lifecycle side_effects must be a list: {hook_id}")
        if side_effects:
            permission = hook.get("permission")
            if not isinstance(permission, str) or not permission.startswith("$"):
                raise RoleDirectoryError(f"side-effecting role lifecycle hook requires permission binding: {hook_id}")
        for binding in hook["bindings"].values():
            if isinstance(binding, str) and binding.startswith("$artifact_type:"):
                artifact_type = binding.split(":", 1)[1]
                if artifact_type not in produced_types:
                    raise RoleDirectoryError(f"role lifecycle hook references unknown artifact type: {artifact_type}")
    return payload


def _validate_workflow(payload: dict[str, Any]) -> None:
    workflow = payload.get("workflow")
    if workflow is None:
        return
    if not isinstance(workflow, dict):
        raise RoleDirectoryError("role directory workflow must be an object")
    initial_state = workflow.get("initial_state")
    if not isinstance(initial_state, list) or any(not isinstance(item, str) or not item for item in initial_state):
        raise RoleDirectoryError("role directory workflow initial_state must be a string list")
    stages = workflow.get("stages")
    if not isinstance(stages, list) or not stages:
        raise RoleDirectoryError("role directory workflow must contain non-empty stages list")
    stage_ids = []
    for stage in stages:
        if not isinstance(stage, dict):
            raise RoleDirectoryError("role workflow stage must be an object")
        stage_id = str(stage.get("stage_id") or "")
        handler_id = str(stage.get("handler_id") or "")
        dependencies = stage.get("depends_on")
        if not stage_id or stage_id in stage_ids:
            raise RoleDirectoryError(f"role workflow stage_id must be unique: {stage_id}")
        if not handler_id:
            raise RoleDirectoryError(f"role workflow stage requires handler_id: {stage_id}")
        effects = stage.get("effects")
        if not isinstance(effects, list) or any(not isinstance(item, str) or not item for item in effects):
            raise RoleDirectoryError(f"role workflow effects must be a string list: {stage_id}")
        if not isinstance(dependencies, list):
            raise RoleDirectoryError(f"role workflow depends_on must be a list: {stage_id}")
        for field in ("requires", "provides"):
            values = stage.get(field)
            if not isinstance(values, list) or any(not isinstance(item, str) or not item for item in values):
                raise RoleDirectoryError(f"role workflow {field} must be a string list: {stage_id}")
        stage_ids.append(stage_id)
    known = set(stage_ids)
    for stage in stages:
        stage_id = str(stage["stage_id"])
        unknown = [str(item) for item in stage["depends_on"] if str(item) not in known]
        if unknown:
            raise RoleDirectoryError(f"role workflow stage references unknown dependency: {stage_id}:{unknown[0]}")


def _validate_v2_role(role_id: str, role: dict[str, Any]) -> None:
    for field in ("contract", "gates", "fallback_policy", "llm_policy", "kb_policy", "stop_conditions", "quality_criteria"):
        if field not in role:
            raise RoleDirectoryError(f"role_directory.v2 role requires {field}: {role_id}")
    contract = role.get("contract")
    if not isinstance(contract, dict):
        raise RoleDirectoryError(f"role contract must be object: {role_id}")
    if not isinstance(contract.get("inputs"), list) or not isinstance(contract.get("outputs"), list):
        raise RoleDirectoryError(f"role contract requires inputs/outputs lists: {role_id}")
    if not isinstance(role.get("gates"), list):
        raise RoleDirectoryError(f"role gates must be list: {role_id}")
    if not isinstance(role.get("stop_conditions"), list):
        raise RoleDirectoryError(f"role stop_conditions must be list: {role_id}")
    if not isinstance(role.get("quality_criteria"), list):
        raise RoleDirectoryError(f"role quality_criteria must be list: {role_id}")
    if not isinstance(role.get("fallback_policy"), dict):
        raise RoleDirectoryError(f"role fallback_policy must be object: {role_id}")
    if not isinstance(role.get("llm_policy"), dict):
        raise RoleDirectoryError(f"role llm_policy must be object: {role_id}")
    if not isinstance(role.get("kb_policy"), dict):
        raise RoleDirectoryError(f"role kb_policy must be object: {role_id}")


def role_entry(role_id: str, *, directory: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = directory or load_role_directory()
    roles = dict(payload.get("roles") or {})
    if role_id not in roles:
        raise RoleDirectoryError(f"unknown role: {role_id}")
    return dict(roles[role_id])


def role_builder_config(role_id: str, *, directory: dict[str, Any] | None = None) -> dict[str, Any]:
    role = role_entry(role_id, directory=directory)
    builder = role.get("artifact_builder")
    if not isinstance(builder, dict):
        raise RoleDirectoryError(f"role has no artifact_builder: {role_id}")
    return dict(builder)


def pipeline_steps(*, directory: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    payload = directory or load_role_directory()
    return [dict(step) for step in list(payload.get("pipeline") or [])]


def pipeline_step_for_role(role_id: str, *, directory: dict[str, Any] | None = None) -> dict[str, Any]:
    for step in pipeline_steps(directory=directory):
        if step.get("role_id") == role_id:
            return step
    raise RoleDirectoryError(f"role is not runnable in configured pipeline: {role_id}")


def role_for_output_key(output_key: str, *, directory: dict[str, Any] | None = None) -> str:
    for step in pipeline_steps(directory=directory):
        if step.get("output_key") == output_key:
            return str(step.get("role_id") or "")
    raise RoleDirectoryError(f"no role produces configured output: {output_key}")


def lifecycle_hooks(*, directory: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    payload = directory or load_role_directory()
    return [dict(row) for row in list(payload.get("lifecycle_hooks") or [])]


def workflow_stages(*, directory: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    payload = directory or load_role_directory()
    return [dict(row) for row in list(dict(payload.get("workflow") or {}).get("stages") or [])]


def workflow_initial_state(*, directory: dict[str, Any] | None = None) -> list[str]:
    payload = directory or load_role_directory()
    return [str(item) for item in list(dict(payload.get("workflow") or {}).get("initial_state") or [])]
