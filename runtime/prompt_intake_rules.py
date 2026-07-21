"""Load prompt intake rules from external configuration."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RULES_PATH = ROOT / "config" / "prompt_intake_rules.json"


class PromptIntakeRulesError(RuntimeError):
    """Raised when prompt intake rules are invalid."""


@lru_cache(maxsize=1)
def load_prompt_intake_rules(path: str | None = None) -> dict[str, Any]:
    source = Path(path) if path else RULES_PATH
    payload = json.loads(source.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "prompt_intake_rules.v1":
        raise PromptIntakeRulesError("prompt intake rules must use schema_version prompt_intake_rules.v1")
    if payload.get("status") != "active":
        raise PromptIntakeRulesError("prompt intake rules must be active")
    for field in (
        "supported_system_types",
        "system_type_rules",
        "dependency_policy_markers",
        "input_markers",
        "output_markers",
        "success_criteria_markers",
        "simple_cli_transform_markers",
        "scope_unbounded_markers",
        "cli_argument_program",
        "boundary_marker_groups",
        "clarification_questions",
    ):
        if field not in payload:
            raise PromptIntakeRulesError(f"prompt intake rules require {field}")
    supported = payload.get("supported_system_types")
    if not isinstance(supported, list) or not supported:
        raise PromptIntakeRulesError("supported_system_types must be a non-empty list")
    for row in payload.get("system_type_rules") or []:
        if not isinstance(row, dict) or row.get("system_type") not in supported:
            raise PromptIntakeRulesError("system_type_rules must reference supported system types")
        if not isinstance(row.get("markers"), list) or not row["markers"]:
            raise PromptIntakeRulesError("system_type_rules rows require non-empty markers")
    boundary = payload.get("boundary_marker_groups")
    if not isinstance(boundary, dict) or not isinstance(boundary.get("unsupported"), dict) or not isinstance(boundary.get("risk"), dict):
        raise PromptIntakeRulesError("boundary_marker_groups requires unsupported and risk maps")
    return payload


def markers(name: str, *, rules: dict[str, Any] | None = None) -> list[str]:
    payload = rules or load_prompt_intake_rules()
    return [str(item) for item in payload.get(name, [])]


def marker_groups(kind: str, *, rules: dict[str, Any] | None = None) -> dict[str, list[str]]:
    payload = rules or load_prompt_intake_rules()
    groups = dict(dict(payload.get("boundary_marker_groups") or {}).get(kind) or {})
    return {str(name): [str(item) for item in values] for name, values in groups.items()}
