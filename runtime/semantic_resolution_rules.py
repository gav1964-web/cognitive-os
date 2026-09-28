"""Load L4.5 semantic resolution rules from external configuration."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RULES_PATH = ROOT / "config" / "semantic_resolution_rules.json"


class SemanticResolutionRulesError(RuntimeError):
    """Raised when semantic resolution rules are invalid."""


@lru_cache(maxsize=1)
def load_semantic_resolution_rules(path: str | None = None) -> dict[str, Any]:
    source = Path(path) if path else RULES_PATH
    payload = json.loads(source.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "semantic_resolution_rules.v1":
        raise SemanticResolutionRulesError("semantic resolution rules must use schema_version semantic_resolution_rules.v1")
    if payload.get("status") != "active":
        raise SemanticResolutionRulesError("semantic resolution rules must be active")
    for field in ("existing_resolution_rules", "developer_request_rules", "default_developer_request"):
        if field not in payload:
            raise SemanticResolutionRulesError(f"semantic resolution rules require {field}")
    for row in payload.get("existing_resolution_rules") or []:
        _validate_existing_rule(row)
    for row in payload.get("developer_request_rules") or []:
        _validate_developer_rule(row)
    default = payload.get("default_developer_request")
    if not isinstance(default, dict) or not default.get("request_id") or not default.get("missing_capability"):
        raise SemanticResolutionRulesError("default_developer_request requires request_id and missing_capability")
    return payload


def _validate_existing_rule(row: Any) -> None:
    if not isinstance(row, dict):
        raise SemanticResolutionRulesError("existing resolution rule must be object")
    for field in ("predicate", "required_template", "resolution_id", "means_used", "verification_plan", "kb_candidate"):
        if field not in row:
            raise SemanticResolutionRulesError(f"existing resolution rule requires {field}")
    if not isinstance(row.get("means_used"), list) or not isinstance(row.get("verification_plan"), list):
        raise SemanticResolutionRulesError("existing resolution means_used and verification_plan must be lists")


def _validate_developer_rule(row: Any) -> None:
    if not isinstance(row, dict):
        raise SemanticResolutionRulesError("developer request rule must be object")
    for field in ("predicate", "request_id", "missing_capability", "problem", "acceptance_focus"):
        if field not in row:
            raise SemanticResolutionRulesError(f"developer request rule requires {field}")
    if not isinstance(row.get("acceptance_focus"), list):
        raise SemanticResolutionRulesError("developer request acceptance_focus must be list")
