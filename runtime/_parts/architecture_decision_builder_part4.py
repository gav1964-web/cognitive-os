from __future__ import annotations

from typing import Any


def _non_goals() -> list[str]:
    return [
        "Do not rewrite the whole project in the first transformation step.",
        "Do not mutate Capability Registry from ArchitectSkill.",
        "Do not promote generated candidates without Foundry dry-run and explicit approval.",
        "Do not replace deterministic runtime validation with role output.",
    ]

def _dedupe_by(rows: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    result = []
    seen = set()
    for row in rows:
        value = row.get(key)
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(row)
    return result

def _dedupe_strings(values: list[str]) -> list[str]:
    result = []
    seen = set()
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result

def _safe_id(value: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "_" for ch in value).strip("_")[:60] or "boundary"
