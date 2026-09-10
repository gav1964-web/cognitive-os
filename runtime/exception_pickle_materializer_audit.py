"""Audit unsupported semantic sample shapes for active exception-pickle reuse."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .exception_pickle_active_application import DEFAULT_APPLICATION_LEDGER
from .exception_pickle_autonomous_shadow import _sample_constructor_value
from .exception_pickle_holdout_transaction import DEFAULT_AUDIT


DEFAULT_MATERIALIZER_AUDIT = Path(
    "artifacts/project_development/exception_pickle_materializer_audit.json"
)


def run_exception_pickle_materializer_audit(
    *,
    root: Path,
    audit_path: Path = DEFAULT_AUDIT,
    application_ledger_path: Path = DEFAULT_APPLICATION_LEDGER,
) -> dict[str, Any]:
    """Build a read-only audit of unsupported constructor sample shapes."""
    root = root.resolve()
    audit = _read_json(root, audit_path)
    ledger = _read_json(root, application_ledger_path)
    applied_keys = _applied_target_keys(ledger)
    rows_by_key = {
        _candidate_key(dict(row)): dict(row)
        for row in audit.get("candidates") or []
        if isinstance(row, dict)
    }
    unsupported_cases: list[dict[str, Any]] = []
    parameter_counter: Counter[str] = Counter()
    recommendation_counter: Counter[str] = Counter()
    examples: dict[str, list[dict[str, str]]] = defaultdict(list)
    for blocked in ledger.get("blocked_cases") or []:
        if not isinstance(blocked, dict) or blocked.get("blocker_kind") != "semantic_sample_shape_unsupported":
            continue
        key = f"{blocked.get('project')}::{blocked.get('target')}"
        if key in applied_keys:
            continue
        row = rows_by_key.get(key)
        if row is None:
            continue
        unsupported = _unsupported_parameters(row)
        if not unsupported:
            continue
        case_recommendations = [_recommend_parameter(name) for name in unsupported]
        for name, recommendation in zip(unsupported, case_recommendations):
            parameter_counter[name] += 1
            recommendation_counter[recommendation] += 1
            if len(examples[name]) < 3:
                examples[name].append({
                    "project": str(blocked.get("project") or ""),
                    "target": str(blocked.get("target") or ""),
                })
        unsupported_cases.append({
            "project": blocked.get("project"),
            "target": blocked.get("target"),
            "required_constructor_parameters": list(row.get("required_constructor_parameters") or []),
            "unsupported_parameters": unsupported,
            "recommendations": case_recommendations,
            "status": "materializer_gap",
        })
    recommendations = [
        {
            "parameter": name,
            "count": count,
            "recommendation": _recommend_parameter(name),
            "sample_strategy": _sample_strategy(name),
            "examples": examples.get(name, []),
        }
        for name, count in parameter_counter.most_common()
    ]
    return {
        "artifact_type": "ExceptionPickleMaterializerAudit",
        "schema_version": "exception_pickle_materializer_audit.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "ready",
        "application_ledger": str(application_ledger_path),
        "unsupported_case_count": len(unsupported_cases),
        "unsupported_parameter_count": sum(parameter_counter.values()),
        "recommendation_summary": dict(sorted(recommendation_counter.items())),
        "recommendations": recommendations,
        "cases": unsupported_cases,
        "source_apply": False,
        "kb_promotion": False,
    }


def _unsupported_parameters(row: dict[str, Any]) -> list[str]:
    required = [str(value) for value in row.get("required_constructor_parameters") or []]
    return [name for name in required if _sample_constructor_value(name) is None]


def _recommend_parameter(name: str) -> str:
    lowered = name.lower()
    if lowered.endswith(("_id", "_key", "_name", "_path", "_url", "_type", "_title")):
        return "candidate_primitive_string"
    if lowered in {"summary", "address", "filepath"}:
        return "candidate_primitive_string"
    if lowered in {"line", "column", "index", "total", "number", "count", "size"}:
        return "candidate_primitive_integer"
    if lowered.endswith(("_version", "_time", "_size", "_count", "_index")):
        return "candidate_primitive_integer"
    if lowered in {"retry_after", "max_length", "amount"}:
        return "candidate_primitive_integer"
    if lowered == "issues":
        return "candidate_list"
    if lowered in {"status", "current", "expected", "actual", "type_"}:
        return "candidate_primitive_string"
    if lowered.endswith(("errors", "items", "messages", "permissions", "roles", "values")):
        return "candidate_list"
    if lowered in {"cooldown", "flag", "param", "transformer", "converter"}:
        return "candidate_named_object"
    if lowered in {"response", "request", "container", "context", "connection_key"}:
        return "object_like_hold"
    if lowered in {"error", "cause", "original", "exception"}:
        return "candidate_exception"
    return "object_like_hold"


def _sample_strategy(name: str) -> str:
    recommendation = _recommend_parameter(name)
    return {
        "candidate_primitive_string": "sample string by parameter name",
        "candidate_primitive_integer": "small deterministic integer",
        "candidate_list": "single-element deterministic list",
        "candidate_named_object": "SimpleNamespace with name/mention fields",
        "candidate_exception": "RuntimeError sample preserving message",
        "object_like_hold": "hold until source-backed object contract exists",
    }[recommendation]


def _candidate_key(row: dict[str, Any]) -> str:
    project = row.get("canonical_project") or row.get("project")
    target = f"{row.get('path')}:{row.get('class_name')}.__init__"
    return f"{project}::{target}"


def _applied_target_keys(ledger: dict[str, Any]) -> set[str]:
    return {
        f"{dict(row).get('project')}::{dict(row).get('target')}"
        for row in ledger.get("cases") or []
        if isinstance(row, dict) and row.get("status") == "applied_active_kb"
    }


def _read_json(root: Path, path: Path) -> dict[str, Any]:
    resolved = path if path.is_absolute() else root / path
    payload = json.loads(resolved.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON artifact must be an object: {resolved}")
    return payload
