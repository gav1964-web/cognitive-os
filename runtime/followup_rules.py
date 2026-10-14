"""Load follow-up prompt rules from external configuration."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RULES_PATH = ROOT / "config" / "followup_rules.json"


class FollowupRulesError(RuntimeError):
    """Raised when follow-up rules are invalid."""


@lru_cache(maxsize=1)
def load_followup_rules(path: str | None = None) -> dict[str, Any]:
    source = Path(path) if path else RULES_PATH
    payload = json.loads(source.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "followup_rules.v1":
        raise FollowupRulesError("follow-up rules must use schema_version followup_rules.v1")
    if payload.get("status") != "active":
        raise FollowupRulesError("follow-up rules must be active")
    for field in (
        "question_markers",
        "change_markers",
        "replacement_action_markers",
        "replacement_reference_markers",
    ):
        values = payload.get(field)
        if not isinstance(values, list) or not values or not all(isinstance(item, str) and item for item in values):
            raise FollowupRulesError(f"follow-up rules require non-empty string list: {field}")
    return payload


def markers(name: str, *, rules: dict[str, Any] | None = None) -> list[str]:
    payload = rules or load_followup_rules()
    return [str(item) for item in payload.get(name, [])]
