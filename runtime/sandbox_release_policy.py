"""Load sandbox release, admission and evaluation policy."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "config" / "sandbox_release_policy.json"


class SandboxReleasePolicyError(RuntimeError):
    """Raised when sandbox release policy is invalid."""


@lru_cache(maxsize=1)
def load_sandbox_release_policy(path: str | None = None) -> dict[str, Any]:
    source = Path(path) if path else POLICY_PATH
    payload = json.loads(source.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "sandbox_release_policy.v1":
        raise SandboxReleasePolicyError("sandbox release policy must use schema_version sandbox_release_policy.v1")
    if payload.get("status") != "active":
        raise SandboxReleasePolicyError("sandbox release policy must be active")
    for field in ("generated_package_evaluation", "sandbox_programmer_admission", "sandbox_implementation_result"):
        if field not in payload:
            raise SandboxReleasePolicyError(f"sandbox release policy requires {field}")
    _require_checks(payload, "generated_package_evaluation")
    _require_checks(payload, "sandbox_programmer_admission")
    implementation = dict(payload.get("sandbox_implementation_result") or {})
    llm_policy = dict(implementation.get("llm_policy") or {})
    if llm_policy.get("llm_output_executed_directly") is not False:
        raise SandboxReleasePolicyError("sandbox implementation policy must forbid executing raw LLM output")
    if implementation.get("promotion_allowed") is not False:
        raise SandboxReleasePolicyError("sandbox implementation policy must forbid promotion")
    return payload


def required_checks(section: str, *, policy: dict[str, Any] | None = None) -> list[str]:
    payload = policy or load_sandbox_release_policy()
    return [str(item) for item in dict(payload.get(section) or {}).get("required_checks", [])]


def sandbox_implementation_policy(*, policy: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = policy or load_sandbox_release_policy()
    return dict(payload.get("sandbox_implementation_result") or {})


def _require_checks(payload: dict[str, Any], section: str) -> None:
    checks = dict(payload.get(section) or {}).get("required_checks")
    if not isinstance(checks, list) or not checks:
        raise SandboxReleasePolicyError(f"{section}.required_checks must be a non-empty list")
