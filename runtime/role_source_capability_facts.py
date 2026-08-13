"""Translate Project Map capability evidence into source-context facts."""

from __future__ import annotations

from typing import Any


def capability_facts(answers: dict[str, Any], readiness: dict[str, Any]) -> dict[str, dict[str, Any]]:
    capabilities = dict(answers.get("3_capabilities") or {})
    facts: dict[str, dict[str, Any]] = {}
    for row in _rows(capabilities.get("pure_transforms")):
        _merge(facts, _source(row), {"kind": "pure_transform", "signature": _signature(row)})
    for row in _rows(capabilities.get("bounded_policy_decisions")):
        _merge(facts, _source(row), {"kind": "bounded_policy", "signature": _signature(row)})
    for row in _rows(capabilities.get("too_broad_functions")):
        _merge(facts, _source(row), {"kind": "broad_function", "loc": row.get("loc")})
    plan = dict(readiness.get("minimal_extraction_plan") or {})
    for row in _rows(plan.get("capabilities_to_extract")):
        _merge(
            facts,
            str(row.get("capability") or ""),
            {
                "candidate_level": row.get("candidate_level"),
                "candidate_score": row.get("candidate_score"),
                "first_contract": row.get("first_contract"),
            },
        )
    return facts


def _rows(value: object) -> list[dict[str, Any]]:
    return [row for row in value or [] if isinstance(row, dict)] if isinstance(value, list) else []


def _source(row: dict[str, Any]) -> str:
    return f"{row.get('path')}:{row.get('name')}" if row.get("path") and row.get("name") else ""


def _signature(row: dict[str, Any]) -> dict[str, Any]:
    return {"args": list(row.get("args") or []), "returns": str(row.get("returns") or "")}


def _merge(facts: dict[str, dict[str, Any]], source: str, values: dict[str, Any]) -> None:
    if source:
        facts.setdefault(source, {}).update(values)
