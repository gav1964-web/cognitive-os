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
    return payload


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
