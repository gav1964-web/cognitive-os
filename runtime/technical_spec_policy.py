"""External TechnicalSpec policy catalog loader."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POLICY_PATH = ROOT / "config" / "technical_spec_policy.json"
EXPECTED_SCHEMA_VERSION = "technical_spec_policy.v1"


@lru_cache(maxsize=8)
def load_technical_spec_policy(path: str | None = None) -> dict[str, Any]:
    policy_path = Path(path).resolve() if path else DEFAULT_POLICY_PATH
    payload = json.loads(policy_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("technical spec policy must be a JSON object")
    schema_version = str(payload.get("schema_version") or "")
    if schema_version != EXPECTED_SCHEMA_VERSION:
        raise ValueError(f"unsupported technical spec policy schema: {schema_version}")
    for section_name in ("snippet_analysis", "contract_type_inference", "semantic_rerank", "architecture_shape_score", "target_binding_policy", "dependency_readiness"):
        if not isinstance(payload.get(section_name), dict):
            raise ValueError(f"missing technical spec policy section: {section_name}")
    return payload


def policy_list(section: dict[str, Any], field: str) -> tuple[str, ...]:
    values = section.get(field) or []
    if not isinstance(values, list):
        raise ValueError(f"technical spec policy field must be a list: {field}")
    return tuple(str(value).lower() for value in values)


def policy_rules(section: dict[str, Any], field: str) -> tuple[dict[str, Any], ...]:
    values = section.get(field) or []
    if not isinstance(values, list):
        raise ValueError(f"technical spec policy rule field must be a list: {field}")
    rules = []
    for value in values:
        if not isinstance(value, dict):
            raise ValueError(f"technical spec policy rule must be an object: {field}")
        rules.append(dict(value))
    return tuple(rules)
