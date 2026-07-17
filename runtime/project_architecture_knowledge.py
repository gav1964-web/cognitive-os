"""Declarative knowledge loading and matching for architecture synthesis."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


KNOWLEDGE_DIR = Path(__file__).resolve().parents[1] / "knowledge" / "architecture_patterns"
KNOWLEDGE_PATH = KNOWLEDGE_DIR / "project_archetypes.json"
CAPABILITY_PATTERNS_PATH = KNOWLEDGE_DIR / "capability_patterns.json"
RISK_PATTERNS_PATH = KNOWLEDGE_DIR / "risk_patterns.json"
PROJECT_LESSONS_PATH = KNOWLEDGE_DIR / "project_lessons.json"
BACKLOG_PATH = KNOWLEDGE_DIR / "backlog.json"


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
    )


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


def _match_auxiliary_patterns(
    facts: dict[str, Any],
    records: list[dict[str, Any]],
    *,
    id_field: str,
    fields: tuple[str, ...],
    limit: int,
) -> list[dict[str, Any]]:
    project_text = _project_text(facts)
    rows = []
    for record in records:
        match = dict(record.get("match") or {})
        needles = _strings(match.get("text_contains_any"))
        if not needles:
            continue
        negative = _strings(match.get("negative_signals") or match.get("negative_contains_any"))
        blocked = [needle for needle in negative if needle.lower() in project_text]
        if blocked:
            continue
        required = _strings(match.get("required_contains_any"))
        if required and not any(needle.lower() in project_text for needle in required):
            continue
        found = [needle for needle in needles if needle.lower() in project_text]
        min_score = int(match.get("min_score") or 1)
        if len(found) < min_score:
            continue
        row = {
            id_field: record.get(id_field),
            "matched_because": found[:5],
            "score": len(found),
        }
        for field in fields:
            row[field] = record.get(field)
        rows.append(row)
    return sorted(rows, key=lambda item: (-int(item["score"]), str(item.get(id_field))))[:limit]


def _match_score(facts: dict[str, Any], rule: dict[str, Any]) -> tuple[int, list[str]]:
    match = dict(rule.get("match") or {})
    if not match:
        return 1, ["fallback rule"]
    score = 0
    reasons: list[str] = []
    framework_text = " ".join(str(item) for item in facts.get("frameworks", [])).lower()
    project_text = _project_text(facts)
    project_name = _project_name(str(facts.get("root") or "")).lower()
    input_text = " ".join(str(item) for item in facts.get("inputs", [])).lower()

    negative = _strings(match.get("negative_contains_any") or match.get("negative_signals"))
    blocked = [needle for needle in negative if needle.lower() in project_text]
    if blocked:
        return 0, []

    required = _strings(match.get("required_contains_any"))
    if required and not any(needle.lower() in project_text for needle in required):
        return 0, []

    project_names = _strings(match.get("project_name_contains_any"))
    project_name_matched = False
    if project_names:
        found = [needle for needle in project_names if needle.lower() in project_name]
        if found:
            project_name_matched = True
            score += 60 + len(found) * 10
            reasons.append("project name contains " + ", ".join(found[:3]))

    frameworks = _strings(match.get("framework_contains_any"))
    if frameworks:
        found = [needle for needle in frameworks if needle.lower() in framework_text]
        if not found and not project_name_matched:
            return 0, []
        if found:
            score += 40 + len(found) * 5
            reasons.append("framework contains " + ", ".join(found[:3]))

    text_needles = _strings(match.get("text_contains_any"))
    if text_needles:
        found = [needle for needle in text_needles if needle.lower() in project_text]
        if not found and not project_name_matched:
            return 0, []
        if found:
            score += 30 + len(found) * 3
            reasons.append("project text contains " + ", ".join(found[:4]))

    input_needles = _strings(match.get("input_contains_any"))
    if input_needles:
        found = [needle for needle in input_needles if needle.lower() in input_text]
        if not found and not project_name_matched:
            return 0, []
        if found:
            score += 15 + len(found) * 3
            reasons.append("inputs contain " + ", ".join(found[:3]))

    routes_min = match.get("routes_min")
    if routes_min is not None:
        routes = int(facts.get("routes_count") or 0)
        if routes < int(routes_min):
            return 0, []
        score += 10
        reasons.append(f"routes >= {routes_min}")
    min_score = int(match.get("min_score") or 0)
    if min_score and score < min_score:
        return 0, []
    return score, reasons


def _project_text(facts: dict[str, Any]) -> str:
    runtime = dict(facts.get("runtime_extraction", {}))
    parts = (
        [_project_name(str(facts.get("root") or ""))]
        + [str(item) for item in facts.get("frameworks", [])]
        + [str(item) for item in facts.get("inputs", [])]
        + [str(item) for item in facts.get("outputs", [])]
        + facts.get("central", [])
        + facts.get("broad", [])
        + facts.get("capabilities", [])
        + facts.get("entrypoints", [])
        + facts.get("scenarios", [])
        + [str(item) for item in facts.get("schemas", [])]
        + [str(item) for item in facts.get("weak_contracts", [])]
        + [str(item) for item in facts.get("errors", [])]
        + [str(item) for item in facts.get("handlers", [])]
        + [str(item) for item in facts.get("loop", [])]
        + [str(item) for item in facts.get("risks", [])]
        + [str(row) for row in facts.get("subsystems", [])]
        + [str(row) for row in facts.get("hotspots", [])]
        + [str(row) for row in facts.get("boundaries", [])]
        + [_target(row) for row in runtime.get("process_boundary", [])]
        + [str(row) for row in runtime.get("orchestrators", [])]
        + [str(facts.get("task") or "")]
    )
    return " ".join(str(item) for item in parts).lower()


def _project_name(root: str) -> str:
    if not root:
        return ""
    clean = root.replace("\\", "/").rstrip("/")
    return clean.rsplit("/", 1)[-1]


def _target(item: Any) -> str:
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        return str(item.get("target") or item.get("capability") or "")
    return ""


def _strings(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item)]
    if value in (None, "", []):
        return []
    return [str(value)]
