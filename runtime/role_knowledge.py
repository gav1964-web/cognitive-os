"""Role-scoped view over declarative knowledge records."""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from typing import Any

from .role_definitions import load_role_record_defaults, role_ids


ROLE_ORDER = role_ids()


@dataclass(frozen=True)
class RoleKnowledgeView:
    role: str
    record_count: int
    record_types: dict[str, int]
    record_ids: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def record_roles(record: dict[str, Any]) -> list[str]:
    """Return explicit role scope or a deterministic default for legacy records."""

    explicit = record.get("role_scope")
    if isinstance(explicit, list) and explicit:
        return _known_roles(explicit)
    defaults = load_role_record_defaults()
    fallback = list(ROLE_ORDER[:1]) or ["unassigned"]
    return list(defaults.get(str(record.get("record_type")), fallback))


def evidence_strength(record: dict[str, Any]) -> str:
    """Classify record evidence strength without treating it as truth."""

    explicit = str(record.get("evidence_strength") or "").strip().lower()
    if explicit in {"weak", "medium", "strong", "verified"}:
        return explicit
    if record.get("status") == "implemented_v1":
        return "verified"
    if record.get("record_type") == "project_lesson":
        return "medium"
    if record.get("record_type") in {"project_archetype_rule", "capability_pattern", "risk_pattern"}:
        return "strong"
    return "weak"


def enrich_record_for_role(record: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(record)
    enriched.setdefault("role_scope", record_roles(record))
    enriched.setdefault("evidence_strength", evidence_strength(record))
    return enriched


def role_knowledge_distribution(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize how the current KB is distributed across roles."""

    by_role: dict[str, list[dict[str, Any]]] = {role: [] for role in ROLE_ORDER}
    for record in records:
        enriched = enrich_record_for_role(record)
        for role in enriched["role_scope"]:
            by_role.setdefault(role, []).append(enriched)
    views = []
    for role in ROLE_ORDER:
        rows = by_role.get(role, [])
        record_types = Counter(str(row.get("record_type") or "unknown") for row in rows)
        views.append(
            RoleKnowledgeView(
                role=role,
                record_count=len(rows),
                record_types=dict(sorted(record_types.items())),
                record_ids=[_record_id(row) for row in rows if _record_id(row)][:20],
            ).to_dict()
        )
    return {
        "artifact_type": "RoleKnowledgeDistribution",
        "roles": views,
        "total_records": len(records),
        "policy": {
            "records_are_role_api": True,
            "missing_role_scope_uses_defaults": True,
            "kb_record_is_not_ground_truth": True,
        },
    }


def records_for_role(records: list[dict[str, Any]], role: str) -> list[dict[str, Any]]:
    role = str(role)
    return [enrich_record_for_role(row) for row in records if role in record_roles(row)]


def _record_id(record: dict[str, Any]) -> str:
    for key in ("rule_id", "pattern_id", "risk_id", "lesson_id", "candidate_id"):
        value = record.get(key)
        if value:
            return str(value)
    return ""


def _known_roles(values: list[Any]) -> list[str]:
    known = set(ROLE_ORDER)
    roles = [str(value) for value in values if str(value) in known]
    return roles or list(ROLE_ORDER[:1]) or ["unassigned"]
