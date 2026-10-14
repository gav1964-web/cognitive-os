"""Load static project fact rules from external configuration."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RULES_PATH = ROOT / "config" / "project_fact_rules.json"


class ProjectFactRulesError(RuntimeError):
    """Raised when project fact rules are invalid."""


@lru_cache(maxsize=1)
def load_project_fact_rules(path: str | None = None) -> dict[str, Any]:
    source = Path(path) if path else RULES_PATH
    payload = json.loads(source.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "project_fact_rules.v1":
        raise ProjectFactRulesError("project fact rules must use schema_version project_fact_rules.v1")
    if payload.get("status") != "active":
        raise ProjectFactRulesError("project fact rules must be active")
    if not isinstance(payload.get("question_answer_routes"), list):
        raise ProjectFactRulesError("project fact rules require question_answer_routes")
    for route in payload["question_answer_routes"]:
        if not isinstance(route, dict) or not route.get("answer_key") or not isinstance(route.get("markers"), list):
            raise ProjectFactRulesError("each question_answer_route requires answer_key and markers")
    return payload


def section(name: str, *, rules: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = rules or load_project_fact_rules()
    value = payload.get(name)
    if not isinstance(value, dict):
        raise ProjectFactRulesError(f"unknown project fact rule section: {name}")
    return value


def matches_line(line: str, *, any_markers: list[str] | None = None, all_groups: list[list[str]] | None = None) -> bool:
    lowered = line.lower()
    if any(marker.lower() in lowered for marker in any_markers or []):
        return True
    for group in all_groups or []:
        if all(marker.lower() in lowered for marker in group):
            return True
    return False


def answer_key_for_question(question: str, *, rules: dict[str, Any] | None = None) -> str | None:
    payload = rules or load_project_fact_rules()
    lowered = question.lower()
    best: tuple[int, int, str] | None = None
    for index, route in enumerate(payload.get("question_answer_routes", [])):
        markers = [str(marker).lower() for marker in route.get("markers", [])]
        score = sum(1 for marker in markers if marker in lowered)
        if score <= 0:
            continue
        candidate = (score, -index, str(route["answer_key"]))
        if best is None or candidate > best:
            best = candidate
    return best[2] if best else None
