"""Config-backed advisory solution patterns for Programmer Executor."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DEFAULT_PATH = Path(__file__).resolve().parents[1] / "config" / "executor_solution_patterns.json"


def load_executor_solution_patterns(path: str | Path | None = None) -> dict[str, Any]:
    source = Path(path or DEFAULT_PATH)
    payload = json.loads(source.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "executor_solution_patterns.v1":
        raise ValueError("Unsupported executor solution patterns schema")
    if payload.get("status") != "active":
        raise ValueError("Executor solution patterns must be active")
    _validate_patterns(payload)
    return payload


def select_solution_patterns(context: dict[str, Any]) -> list[dict[str, Any]]:
    catalog = load_executor_solution_patterns()
    rows = []
    for item in list(catalog.get("patterns") or []):
        pattern = dict(item)
        if _matches(dict(pattern.get("match") or {}), context):
            rows.append(_public_pattern(pattern))
    return rows


def _validate_patterns(payload: dict[str, Any]) -> None:
    admission = dict(payload.get("admission_policy") or {})
    if admission.get("automatic_source_mutation_allowed") is not False:
        raise ValueError("executor solution patterns must forbid automatic source mutation")
    seen: set[str] = set()
    for item in list(payload.get("patterns") or []):
        pattern = dict(item)
        pattern_id = str(pattern.get("id") or "")
        if not pattern_id:
            raise ValueError("executor solution pattern requires id")
        if pattern_id in seen:
            raise ValueError(f"duplicate executor solution pattern: {pattern_id}")
        seen.add(pattern_id)
        for field_name in ("match", "action", "safe_next_step", "required_evidence", "risk"):
            if not pattern.get(field_name):
                raise ValueError(f"executor solution pattern {pattern_id} missing {field_name}")


def _matches(match: dict[str, Any], context: dict[str, Any]) -> bool:
    for key, expected in match.items():
        actual = context.get(str(key))
        if isinstance(expected, list):
            if str(actual) not in {str(item) for item in expected}:
                return False
        elif str(actual) != str(expected):
            return False
    return bool(match)


def _public_pattern(pattern: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(pattern.get("id") or ""),
        "label": str(pattern.get("label") or ""),
        "action": str(pattern.get("action") or ""),
        "safe_next_step": str(pattern.get("safe_next_step") or ""),
        "required_evidence": [str(item) for item in list(pattern.get("required_evidence") or [])],
        "risk": str(pattern.get("risk") or ""),
        "confidence": float(pattern.get("confidence") or 0.0),
        "authority": "advisory_pattern_only",
    }
