"""External target-quality policy catalog loader."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POLICY_PATH = ROOT / "config" / "target_quality_policy.json"
EXPECTED_SCHEMA_VERSION = "target_quality_policy.v1"


@lru_cache(maxsize=8)
def load_target_quality_policy(path: str | None = None) -> dict[str, Any]:
    policy_path = Path(path).resolve() if path else DEFAULT_POLICY_PATH
    payload = json.loads(policy_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("target quality policy must be a JSON object")
    schema_version = str(payload.get("schema_version") or "")
    if schema_version != EXPECTED_SCHEMA_VERSION:
        raise ValueError(f"unsupported target quality policy schema: {schema_version}")
    for section_name in ("target_quality", "spec_writer_ranking"):
        section = payload.get(section_name)
        if not isinstance(section, dict):
            raise ValueError(f"missing target quality policy section: {section_name}")
    return payload


def target_quality_section(name: str, *, path: str | None = None) -> dict[str, Any]:
    section = load_target_quality_policy(path).get(name)
    if not isinstance(section, dict):
        raise ValueError(f"missing target quality policy section: {name}")
    return section


def policy_tokens(section: dict[str, Any], field: str) -> tuple[str, ...]:
    values = section.get(field) or []
    if not isinstance(values, list):
        raise ValueError(f"policy field must be a list: {field}")
    return tuple(str(value).lower() for value in values)


def nested_policy_tokens(section: dict[str, Any], nested: str, field: str) -> tuple[str, ...]:
    child = section.get(nested) or {}
    if not isinstance(child, dict):
        raise ValueError(f"policy nested field must be an object: {nested}")
    return policy_tokens(child, field)
