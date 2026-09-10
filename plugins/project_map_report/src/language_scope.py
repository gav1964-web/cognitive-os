"""Classify the implementation-language boundary of a project report."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


DEFAULT_PATH = Path(__file__).resolve().parents[3] / "knowledge" / "architecture_patterns" / "language_scope.json"


@lru_cache(maxsize=4)
def load_language_scope_policy(path: str | None = None) -> dict[str, Any]:
    payload = json.loads((Path(path) if path else DEFAULT_PATH).read_text(encoding="utf-8"))
    if payload.get("schema_version") != "language_scope.v1":
        raise ValueError("language scope KB must use schema_version language_scope.v1")
    for section in ("implementation_languages", "foreign_dominance", "limited_scope", "provenance"):
        if not isinstance(payload.get(section), dict):
            raise ValueError(f"language scope KB must define {section}")
    return payload


def language_scope(stack: dict[str, Any]) -> dict[str, Any]:
    policy = load_language_scope_policy()
    counts = _implementation_counts(stack, policy["implementation_languages"])
    python_count = counts.get("Python", 0)
    foreign = [(name, count) for name, count in counts.items() if name != "Python"]
    dominant_name, dominant_count = max(foreign, key=lambda row: row[1], default=("Python", python_count))
    threshold = policy["foreign_dominance"]
    foreign_dominated = dominant_count >= int(threshold["minimum_files"]) and dominant_count >= max(
        1, python_count * int(threshold["ratio_over_python"])
    )
    if not foreign_dominated:
        return {"status": "full", "primary_language": "Python", "language_counts": counts}
    limited = policy["limited_scope"]
    return {
        "status": limited["status"],
        "reason_code": limited["reason_code"],
        "primary_language": dominant_name,
        "analyzed_boundary": limited["analyzed_boundary"],
        "language_counts": counts,
    }


def _implementation_counts(stack: dict[str, Any], groups: dict[str, list[str]]) -> dict[str, int]:
    raw = {str(row.get("language")): int(row.get("files") or 0) for row in stack.get("languages", [])}
    return {name: sum(raw.get(label, 0) for label in labels) for name, labels in groups.items()}
