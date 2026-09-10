"""Append-only telemetry for knowledge-base usage in real runs."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_TELEMETRY_PATH = Path("artifacts") / "telemetry" / "knowledge_usage.jsonl"


def record_knowledge_usage(
    *,
    event_type: str,
    role: str,
    source: str,
    root: Path | str | None = None,
    rule_id: str | None = None,
    status: str | None = None,
    confidence: float | str | None = None,
    gap_id: str | None = None,
    query: str | None = None,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Persist one normalized KB usage event and return the written payload."""

    payload = {
        "artifact_type": "KnowledgeUsageEvent",
        "schema_version": "1.0",
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        "role": role,
        "source": source,
        "rule_id": rule_id,
        "status": status,
        "confidence": confidence,
        "gap_id": gap_id,
        "query": query,
        "details": details or {},
    }
    path = telemetry_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
    return payload


def telemetry_path(root: Path | str | None = None) -> Path:
    base = Path(root) if root is not None else Path.cwd()
    return base / DEFAULT_TELEMETRY_PATH


def load_knowledge_usage_events(root: Path | str | None = None) -> list[dict[str, Any]]:
    path = telemetry_path(root)
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def knowledge_usage_summary(root: Path | str | None = None) -> dict[str, Any]:
    events = load_knowledge_usage_events(root)
    by_event_type = Counter(str(row.get("event_type")) for row in events)
    by_role = Counter(str(row.get("role")) for row in events)
    by_source = Counter(str(row.get("source")) for row in events)
    by_status = Counter(str(row.get("status")) for row in events)
    by_rule = Counter(str(row.get("rule_id")) for row in events if row.get("rule_id"))
    return {
        "artifact_type": "KnowledgeUsageSummary",
        "schema_version": "1.0",
        "event_count": len(events),
        "by_event_type": dict(by_event_type),
        "by_role": dict(by_role),
        "by_source": dict(by_source),
        "by_status": dict(by_status),
        "top_rules": by_rule.most_common(20),
        "telemetry_path": telemetry_path(root).as_posix(),
    }
