"""Load sandbox programmer profile policy from external configuration."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PROFILES_PATH = ROOT / "config" / "sandbox_programmer_profiles.json"


class SandboxProgrammerProfilesError(RuntimeError):
    """Raised when sandbox programmer profile configuration is invalid."""


@lru_cache(maxsize=1)
def load_sandbox_programmer_profiles(path: str | None = None) -> dict[str, Any]:
    source = Path(path) if path else PROFILES_PATH
    payload = json.loads(source.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "sandbox_programmer_profiles.v1":
        raise SandboxProgrammerProfilesError("sandbox programmer profiles must use schema_version sandbox_programmer_profiles.v1")
    if payload.get("status") != "active":
        raise SandboxProgrammerProfilesError("sandbox programmer profiles must be active")
    profiles = payload.get("profiles")
    if not isinstance(profiles, dict) or not profiles:
        raise SandboxProgrammerProfilesError("profiles must be a non-empty object")
    for profile, row in profiles.items():
        if not isinstance(row, dict):
            raise SandboxProgrammerProfilesError(f"profile must be object: {profile}")
        for field in ("expression_policy", "graph_family", "admission_shape"):
            if field not in row:
                raise SandboxProgrammerProfilesError(f"profile {profile} requires {field}")
    for field in ("text_expression_policy", "numeric_expression_policy"):
        if not isinstance(payload.get(field), dict):
            raise SandboxProgrammerProfilesError(f"{field} must be object")
    return payload


def profile_entry(profile: str, *, profiles: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = profiles or load_sandbox_programmer_profiles()
    rows = dict(payload.get("profiles") or {})
    if profile not in rows:
        raise SandboxProgrammerProfilesError(f"unsupported sandbox operation profile: {profile}")
    return dict(rows[profile])


def allowed_profiles(*, profiles: dict[str, Any] | None = None) -> set[str]:
    payload = profiles or load_sandbox_programmer_profiles()
    return {str(item) for item in dict(payload.get("profiles") or {})}


def expression_policy(profile: str, *, profiles: dict[str, Any] | None = None) -> str:
    return str(profile_entry(profile, profiles=profiles).get("expression_policy") or "")


def graph_family(profile: str, *, profiles: dict[str, Any] | None = None) -> str:
    return str(profile_entry(profile, profiles=profiles).get("graph_family") or "")


def admission_shape(profile: str, *, profiles: dict[str, Any] | None = None) -> str:
    return str(profile_entry(profile, profiles=profiles).get("admission_shape") or "")
