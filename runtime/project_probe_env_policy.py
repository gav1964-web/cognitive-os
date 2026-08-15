"""Config-backed dependency policy for probe environment preparation."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POLICY_PATH = ROOT / "config" / "project_probe_env_policy.json"
EXPECTED_SCHEMA_VERSION = "project_probe_env_policy.v1"


@lru_cache(maxsize=8)
def load_project_probe_env_policy(path: str | None = None) -> dict[str, Any]:
    source = Path(path).resolve() if path else DEFAULT_POLICY_PATH
    payload = json.loads(source.read_text(encoding="utf-8"))
    if payload.get("schema_version") != EXPECTED_SCHEMA_VERSION:
        raise ValueError(f"unsupported project probe env policy schema: {payload.get('schema_version')}")
    if payload.get("status") != "active":
        raise ValueError("project probe env policy must be active")
    for field_name in (
        "package_to_module",
        "heavy_or_external",
        "native_or_compiled",
        "wheel_only_native_allowlist",
        "package_companions",
        "low_risk_allowlist",
        "internal_probe_stubs",
        "isolated_dependency_profile",
    ):
        value = payload.get(field_name)
        if not isinstance(value, (dict, list)) or not value:
            raise ValueError(f"project probe env policy field must be a non-empty object or list: {field_name}")
    native = set(_strings(payload["native_or_compiled"]))
    wheel = set(_strings(payload["wheel_only_native_allowlist"]))
    if not wheel <= native:
        raise ValueError("wheel_only_native_allowlist must be a subset of native_or_compiled")
    isolated = dict(payload["isolated_dependency_profile"])
    for field_name in ("environment_kind", "env_path_template", "verification_gates", "forbidden_actions"):
        if not isolated.get(field_name):
            raise ValueError(f"isolated dependency profile policy requires: {field_name}")
    return payload


def _strings(value: object) -> list[str]:
    return [str(item) for item in list(value or [])]


_POLICY = load_project_probe_env_policy()
PACKAGE_TO_MODULE = {str(key): str(value) for key, value in dict(_POLICY["package_to_module"]).items()}
HEAVY_OR_EXTERNAL = set(_strings(_POLICY["heavy_or_external"]))
NATIVE_OR_COMPILED = set(_strings(_POLICY["native_or_compiled"]))
WHEEL_ONLY_NATIVE_ALLOWLIST = set(_strings(_POLICY["wheel_only_native_allowlist"]))
PACKAGE_COMPANIONS = {
    str(key): _strings(value)
    for key, value in dict(_POLICY["package_companions"]).items()
}
LOW_RISK_ALLOWLIST = set(_strings(_POLICY["low_risk_allowlist"]))
INTERNAL_PROBE_STUBS = set(_strings(_POLICY["internal_probe_stubs"]))
