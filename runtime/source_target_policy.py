"""Shared source-target safety policy for role handoffs."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POLICY_PATH = ROOT / "config" / "role_source_policy.json"
EXPECTED_SCHEMA_VERSION = "role_source_policy.v1"


@lru_cache(maxsize=8)
def load_role_source_policy(path: str | None = None) -> dict[str, Any]:
    policy_path = Path(path).resolve() if path else DEFAULT_POLICY_PATH
    payload = json.loads(policy_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("role source policy must be a JSON object")
    schema_version = str(payload.get("schema_version") or "")
    if schema_version != EXPECTED_SCHEMA_VERSION:
        raise ValueError(f"unsupported role source policy schema: {schema_version}")
    if payload.get("status") != "active":
        raise ValueError("role source policy must be active")
    section = payload.get("implementation_target_policy")
    if not isinstance(section, dict):
        raise ValueError("missing implementation_target_policy")
    for field_name in ("context_only_path_tokens", "context_only_file_tokens", "blocked_by"):
        if not isinstance(section.get(field_name), list) or not section.get(field_name):
            raise ValueError(f"role source policy field must be a non-empty list: {field_name}")
    if not section.get("blocked_status") or not section.get("selection_reason"):
        raise ValueError("role source policy missing blocked status or selection reason")
    scope = payload.get("scope_selection_policy")
    if not isinstance(scope, dict):
        raise ValueError("missing scope_selection_policy")
    for field_name in (
        "candidate_excluded_dirs",
        "candidate_noise_parts",
        "candidate_noise_suffixes",
        "disfavored_roots",
        "manifest_names",
        "preferred_roots",
        "syntax_fixture_roots",
    ):
        if not isinstance(scope.get(field_name), list) or not scope.get(field_name):
            raise ValueError(f"scope selection policy field must be a non-empty list: {field_name}")
    return payload


def implementation_target_violation(source: str, policy: dict[str, Any] | None = None) -> dict[str, Any]:
    if not source or source.startswith("greenfield:"):
        return {"status": "allowed", "matched_tokens": []}
    row = dict((policy or load_role_source_policy()).get("implementation_target_policy") or {})
    matched = _matched_tokens(source, row)
    if not matched:
        return {"status": "allowed", "matched_tokens": []}
    return {
        "status": str(row.get("blocked_status") or "blocked_no_safe_candidate"),
        "matched_tokens": matched,
        "blocked_by": [str(item) for item in list(row.get("blocked_by") or [])],
        "selection_reason": str(row.get("selection_reason") or "context-only implementation target"),
    }


def is_context_only_implementation_target(source: str, policy: dict[str, Any] | None = None) -> bool:
    return implementation_target_violation(source, policy).get("status") != "allowed"


def is_fallback_product_target(source: str, policy: dict[str, Any] | None = None) -> bool:
    row = dict((policy or load_role_source_policy()).get("implementation_target_policy") or {})
    normalized = "/" + source.replace("\\", "/").lower().lstrip("/")
    return any(str(token).lower() in normalized for token in list(row.get("fallback_product_path_tokens") or []))


def scope_selection_policy(policy: dict[str, Any] | None = None) -> dict[str, Any]:
    return dict((policy or load_role_source_policy()).get("scope_selection_policy") or {})


def scope_policy_list(field_name: str, policy: dict[str, Any] | None = None) -> list[str]:
    return [str(item) for item in list(scope_selection_policy(policy).get(field_name) or [])]


def scope_policy_int(field_name: str, default: int, policy: dict[str, Any] | None = None) -> int:
    value = scope_selection_policy(policy).get(field_name)
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _matched_tokens(source: str, row: dict[str, Any]) -> list[str]:
    normalized = "/" + source.replace("\\", "/").lower()
    tokens = [str(item).lower() for item in list(row.get("context_only_path_tokens") or [])]
    tokens.extend(str(item).lower() for item in list(row.get("context_only_file_tokens") or []))
    return [token for token in tokens if token and token in normalized]
