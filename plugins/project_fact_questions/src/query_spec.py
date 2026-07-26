"""Config-driven ProjectFactQuerySpec parser and executor."""

from __future__ import annotations

import json
import re
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
PATTERNS_PATH = ROOT / "config" / "project_fact_query_patterns.json"


def query_answers(questions: list[str], file_rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    answers: dict[str, dict[str, Any]] = {}
    payload = load_query_patterns()
    for question in _questions_with_defaults(questions, payload):
        spec = parse_query_spec(question, patterns=payload)
        if spec is None:
            continue
        answers[str(spec["answer_key"])] = execute_query_spec(spec, file_rows)
    return answers


def selected_query_answer(question: str, answers: dict[str, Any]) -> tuple[str, dict[str, Any]] | None:
    spec = parse_query_spec(question)
    if spec is None:
        return None
    answer_key = str(spec["answer_key"])
    answer = answers.get(answer_key)
    if isinstance(answer, dict):
        return answer_key, answer
    return None


def parse_query_spec(question: str, *, patterns: dict[str, Any] | None = None) -> dict[str, Any] | None:
    payload = patterns or load_query_patterns()
    lowered = question.lower()
    facts = _extracted_facts(lowered)
    for pattern in payload.get("patterns", []):
        if not isinstance(pattern, dict) or not _matches_pattern(lowered, pattern):
            continue
        spec = _build_spec(pattern, facts)
        if spec is not None:
            return spec
    return None


def execute_query_spec(spec: dict[str, Any], file_rows: list[dict[str, Any]]) -> dict[str, Any]:
    rows = [_normalize_file_row(row) for row in file_rows]
    for flt in spec.get("filters", []):
        if isinstance(flt, dict):
            rows = [row for row in rows if _matches_filter(row, flt)]
    for sort in reversed([row for row in spec.get("sort", []) if isinstance(row, dict)]):
        field = str(sort.get("field") or "path")
        reverse = str(sort.get("direction") or "asc") == "desc"
        rows.sort(key=lambda row: row.get(field), reverse=reverse)
    limit = spec.get("limit")
    limited = rows[: int(limit)] if isinstance(limit, int) and limit > 0 else rows
    output_fields = [str(field) for field in spec.get("output_fields", []) if field]
    result = {
        "artifact_type": "ProjectFactQueryResult",
        "query_spec": spec,
        "count": len(rows),
        "count_total": len(rows),
        "count_returned": len(limited),
        "rows": [{field: row.get(field) for field in output_fields} for row in limited],
        "files": [{field: row.get(field) for field in output_fields} for row in limited],
    }
    result.update(_threshold_metadata(spec))
    return result


def load_query_patterns() -> dict[str, Any]:
    path = PATTERNS_PATH
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "project_fact_query_patterns.v1":
        raise ValueError("project fact query patterns schema mismatch")
    if payload.get("status") != "active":
        raise ValueError("project fact query patterns must be active")
    return payload


def _questions_with_defaults(questions: list[str], payload: dict[str, Any]) -> list[str]:
    defaults = [str(item) for item in payload.get("default_questions", []) if item]
    return defaults + [question for question in questions if question not in defaults]


def _matches_pattern(lowered: str, pattern: dict[str, Any]) -> bool:
    for group in pattern.get("all_markers", []):
        if not isinstance(group, list):
            return False
        if not any(str(marker).lower() in lowered for marker in group):
            return False
    return True


def _build_spec(pattern: dict[str, Any], facts: dict[str, Any]) -> dict[str, Any] | None:
    filters = []
    for flt in pattern.get("filters", []):
        if not isinstance(flt, dict):
            continue
        resolved = dict(flt)
        if "value_from" in resolved:
            value = facts.get(str(resolved.pop("value_from")))
            if value is None:
                return None
            resolved["value"] = value
        filters.append(resolved)
    limit = pattern.get("limit")
    if limit is None and pattern.get("limit_from"):
        limit = facts.get(str(pattern["limit_from"])) or pattern.get("default_limit")
    answer_key = _format_answer_key(str(pattern.get("answer_key_template") or pattern.get("id")), facts, limit)
    return {
        "artifact_type": "ProjectFactQuerySpec",
        "pattern_id": pattern.get("id"),
        "target": pattern.get("target"),
        "filters": filters,
        "sort": list(pattern.get("sort", [])),
        "limit": limit,
        "output_fields": list(pattern.get("output_fields", [])),
        "answer_key": answer_key,
    }


def _format_answer_key(template: str, facts: dict[str, Any], limit: Any) -> str:
    values = dict(facts)
    values["limit"] = limit
    return template.format(**values)


def _extracted_facts(lowered: str) -> dict[str, Any]:
    facts: dict[str, Any] = {}
    integer = re.search(r"\d{1,9}", lowered)
    if integer:
        facts["first_integer"] = int(integer.group(0))
    top = re.search(r"(?:топ|top)\s*(\d{1,4})", lowered)
    if top:
        facts["top_integer"] = max(1, min(int(top.group(1)), 1000))
    size = re.search(r"(\d+(?:[.,]\d+)?)\s*(kb|кб|kib|mb|мб|mib|bytes?|байт)", lowered)
    if size:
        value = float(size.group(1).replace(",", "."))
        unit = size.group(2)
        multiplier = 1
        label_unit = "bytes"
        if unit in {"kb", "кб", "kib"}:
            multiplier = 1024
            label_unit = "kb"
        elif unit in {"mb", "мб", "mib"}:
            multiplier = 1024 * 1024
            label_unit = "mb"
        size_bytes = max(1, min(int(value * multiplier), 10_000_000_000))
        facts["first_size_bytes"] = size_bytes
        facts["first_size_label"] = f"{int(value) if value.is_integer() else str(value).replace('.', '_')}_{label_unit}"
    return facts


def _normalize_file_row(row: dict[str, Any]) -> dict[str, Any]:
    path = str(row.get("path") or "")
    size_bytes = int(row.get("size_bytes") or 0)
    normalized = dict(row)
    normalized["path"] = path
    normalized["name"] = PurePosixPath(path.replace("\\", "/")).name
    normalized["extension"] = str(row.get("extension") or PurePosixPath(path).suffix)
    normalized["size_bytes"] = size_bytes
    normalized["size_kb"] = round(size_bytes / 1024, 2)
    normalized["line_count"] = int(row.get("line_count") or 0)
    return normalized


def _matches_filter(row: dict[str, Any], flt: dict[str, Any]) -> bool:
    field = str(flt.get("field") or "")
    op = str(flt.get("op") or "")
    expected = flt.get("value")
    actual = row.get(field)
    if op == "eq":
        return actual == expected
    if op == "contains":
        return str(expected) in str(actual)
    if op == "gt":
        return _number(actual) > _number(expected)
    return False


def _threshold_metadata(spec: dict[str, Any]) -> dict[str, Any]:
    for flt in spec.get("filters", []):
        if not isinstance(flt, dict) or flt.get("op") != "gt":
            continue
        field = flt.get("field")
        value = flt.get("value")
        if field == "line_count":
            return {"threshold": value}
        if field == "size_bytes":
            return {
                "threshold_bytes": value,
                "threshold_kb": round(_number(value) / 1024, 2),
            }
    return {}


def _number(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
