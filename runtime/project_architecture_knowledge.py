"""Declarative knowledge loading and matching for architecture synthesis."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from .project_architecture_matching import (
    contains_marker as _contains_marker,
    match_auxiliary_patterns as _match_auxiliary_patterns,
    match_score as _match_score,
)

KNOWLEDGE_DIR = Path(__file__).resolve().parents[1] / "knowledge" / "architecture_patterns"
KNOWLEDGE_PATH = KNOWLEDGE_DIR / "project_archetypes.json"
CAPABILITY_PATTERNS_PATH = KNOWLEDGE_DIR / "capability_patterns.json"
RISK_PATTERNS_PATH = KNOWLEDGE_DIR / "risk_patterns.json"
PROJECT_LESSONS_PATH = KNOWLEDGE_DIR / "project_lessons.json"
BACKLOG_PATH = KNOWLEDGE_DIR / "backlog.json"
ROLE_QA_PATH = Path(__file__).resolve().parents[1] / "knowledge" / "role_qa" / "synthetic_role_qa.json"
@lru_cache(maxsize=1)
def load_architecture_knowledge(path: str | None = None) -> dict[str, Any]:
    """Load declarative project architecture rules from the knowledge base."""

    source = Path(path) if path else KNOWLEDGE_PATH
    payload = json.loads(source.read_text(encoding="utf-8"))
    records = payload.get("records")
    if not isinstance(records, list):
        raise ValueError("architecture knowledge must contain records array")
    normalized = []
    for row in records:
        if not isinstance(row, dict):
            continue
        if row.get("record_type") != "project_archetype_rule":
            continue
        if not row.get("rule_id") or not row.get("archetype") or not row.get("label"):
            raise ValueError("project_archetype_rule requires rule_id, archetype, and label")
        normalized.append(row)
    payload["records"] = sorted(normalized, key=lambda item: (-int(item.get("priority") or 0), str(item.get("rule_id"))))
    return payload


@lru_cache(maxsize=1)
def load_capability_patterns(path: str | None = None) -> dict[str, Any]:
    payload = _load_records(Path(path) if path else CAPABILITY_PATTERNS_PATH, "capability_pattern", "pattern_id")
    return payload


@lru_cache(maxsize=1)
def load_risk_patterns(path: str | None = None) -> dict[str, Any]:
    payload = _load_records(Path(path) if path else RISK_PATTERNS_PATH, "risk_pattern", "risk_id")
    return payload


@lru_cache(maxsize=1)
def load_project_lessons(path: str | None = None) -> dict[str, Any]:
    payload = _load_records(Path(path) if path else PROJECT_LESSONS_PATH, "project_lesson", "lesson_id")
    return payload


@lru_cache(maxsize=1)
def load_knowledge_backlog(path: str | None = None) -> dict[str, Any]:
    payload = _load_records(Path(path) if path else BACKLOG_PATH, "architecture_pattern_backlog_item", "pattern_id")
    return payload


def load_all_knowledge_records() -> list[dict[str, Any]]:
    """Return all advisory KB records that participate in role distribution."""

    return (
        list(load_architecture_knowledge().get("records", []))
        + list(load_capability_patterns().get("records", []))
        + list(load_risk_patterns().get("records", []))
        + list(load_project_lessons().get("records", []))
        + list(load_knowledge_backlog().get("records", []))
        + load_role_qa_records()
    )


def load_role_qa_records(path: str | None = None) -> list[dict[str, Any]]:
    """Load role-scoped Q/A records that live inside the KB."""

    source = Path(path) if path else ROLE_QA_PATH
    if not source.is_file():
        return []
    payload = json.loads(source.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "synthetic_role_qa.v1":
        raise ValueError("role QA KB must use schema_version synthetic_role_qa.v1")
    records = payload.get("records")
    if not isinstance(records, list):
        raise ValueError("role QA KB must contain records array")
    return [dict(row) for row in records if isinstance(row, dict) and row.get("record_type") == "role_qa"]


def _load_records(path: Path, record_type: str, id_field: str) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    records = payload.get("records")
    if not isinstance(records, list):
        raise ValueError(f"{path.name} must contain records array")
    normalized = []
    for row in records:
        if not isinstance(row, dict) or row.get("record_type") != record_type:
            continue
        if not row.get(id_field):
            raise ValueError(f"{record_type} requires {id_field}")
        normalized.append(row)
    payload["records"] = normalized
    return payload


def match_capability_patterns(facts: dict[str, Any], *, limit: int = 8) -> list[dict[str, Any]]:
    return _match_auxiliary_patterns(
        facts,
        load_capability_patterns().get("records", []),
        id_field="pattern_id",
        fields=("label", "contract_hint", "test_strategy", "first_slice_hint"),
        limit=limit,
    )


def match_risk_patterns(facts: dict[str, Any], *, limit: int = 8) -> list[dict[str, Any]]:
    return _match_auxiliary_patterns(
        facts,
        load_risk_patterns().get("records", []),
        id_field="risk_id",
        fields=("severity", "risk", "mitigation"),
        limit=limit,
    )


def match_project_lessons(
    rule: dict[str, Any],
    capability_patterns: list[dict[str, Any]],
    risk_patterns: list[dict[str, Any]],
    *,
    limit: int = 6,
) -> list[dict[str, Any]]:
    tags = {
        str(rule.get("rule_id") or ""),
        str(rule.get("archetype") or ""),
        *[str(row.get("pattern_id") or "") for row in capability_patterns],
        *[str(row.get("risk_id") or "") for row in risk_patterns],
    }
    rows = []
    for lesson in load_project_lessons().get("records", []):
        applies = {str(item) for item in lesson.get("applies_to", [])}
        if tags & applies:
            rows.append(
                {
                    "lesson_id": lesson.get("lesson_id"),
                    "source": lesson.get("source"),
                    "lesson": lesson.get("lesson"),
                    "applies_to": lesson.get("applies_to", []),
                    "evidence": lesson.get("evidence", []),
                }
            )
    return rows[:limit]


def match_architecture_rule(facts: dict[str, Any], knowledge: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return the best matching declarative architecture rule with evidence."""

    knowledge = knowledge or load_architecture_knowledge()
    candidates = []
    fallback = None
    for rule in knowledge.get("records", []):
        score, reasons = _match_score(facts, rule)
        row = {"rule_id": rule.get("rule_id"), "score": score, "matched_because": reasons}
        if rule.get("archetype") == "python_project":
            fallback = {"rule": rule, **row}
        if score > 0:
            candidates.append({"rule": rule, **row})
    if candidates:
        candidates.sort(key=lambda item: (-int(item["score"]), -int(item["rule"].get("priority") or 0), str(item["rule_id"])))
        best = candidates[0]
    elif fallback:
        best = fallback
    else:
        raise ValueError("architecture knowledge has no usable fallback rule")
    return {
        "rule": best["rule"],
        "score": best["score"],
        "matched_because": best["matched_because"],
        "candidate_rules": [
            {"rule_id": row["rule_id"], "score": row["score"], "matched_because": row["matched_because"][:4]}
            for row in candidates[:5]
        ],
    }
