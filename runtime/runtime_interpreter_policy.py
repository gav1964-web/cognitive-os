"""Load the configuration-first policy for L4/L4.5 runtime changes."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "config" / "runtime_interpreter_policy.json"


class RuntimeInterpreterPolicyError(RuntimeError):
    """Raised when runtime interpreter policy is invalid."""


@lru_cache(maxsize=1)
def load_runtime_interpreter_policy(path: str | None = None) -> dict[str, Any]:
    source = Path(path) if path else POLICY_PATH
    payload = json.loads(source.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "runtime_interpreter_policy.v1":
        raise RuntimeInterpreterPolicyError("runtime interpreter policy must use schema_version runtime_interpreter_policy.v1")
    if payload.get("status") != "active":
        raise RuntimeInterpreterPolicyError("runtime interpreter policy must be active")
    for field in (
        "configuration_first_layers",
        "default_task_change_route",
        "code_change_allowed_only_for",
        "code_change_forbidden_for",
        "target_distribution",
        "required_evidence_before_code_change",
    ):
        if field not in payload:
            raise RuntimeInterpreterPolicyError(f"runtime interpreter policy requires {field}")
    if not {"L4", "L4.5"}.issubset(set(payload["configuration_first_layers"])):
        raise RuntimeInterpreterPolicyError("runtime interpreter policy must cover L4 and L4.5")
    distribution = dict(payload.get("target_distribution") or {})
    if int(distribution.get("configuration_or_registry_change_percent") or 0) < 90:
        raise RuntimeInterpreterPolicyError("configuration-first target must be at least 90 percent")
    if "executing raw LLM output" not in payload["code_change_forbidden_for"]:
        raise RuntimeInterpreterPolicyError("runtime interpreter policy must forbid executing raw LLM output")
    return payload


def default_change_route(task_kind: str, *, policy: dict[str, Any] | None = None) -> str:
    payload = policy or load_runtime_interpreter_policy()
    routes = dict(payload.get("default_task_change_route") or {})
    return str(routes.get(task_kind) or "developer_review_required")


def code_change_requires_evidence(*, policy: dict[str, Any] | None = None) -> list[str]:
    payload = policy or load_runtime_interpreter_policy()
    return [str(item) for item in payload.get("required_evidence_before_code_change", [])]
