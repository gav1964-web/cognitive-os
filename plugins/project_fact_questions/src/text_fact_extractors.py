"""Config-driven text fact extractors for Project Analyzer evidence."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
EXTRACTORS_PATH = ROOT / "config" / "project_text_fact_extractors.json"


def text_fact_answers(tree: dict[str, Any], python_structure: dict[str, Any]) -> dict[str, dict[str, Any]]:
    payload = load_text_fact_extractors()
    answers: dict[str, dict[str, Any]] = {}
    for extractor in payload.get("extractors", []):
        if not isinstance(extractor, dict):
            continue
        answer_key = str(extractor.get("answer_key") or "")
        if extractor.get("extractor_type") == "regex_best_match":
            answers[answer_key] = _regex_best_match(extractor, tree, python_structure)
    return answers


def load_text_fact_extractors() -> dict[str, Any]:
    payload = json.loads(EXTRACTORS_PATH.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "project_text_fact_extractors.v1":
        raise ValueError("project text fact extractors schema mismatch")
    if payload.get("status") != "active":
        raise ValueError("project text fact extractors must be active")
    return payload


def _regex_best_match(
    extractor: dict[str, Any], tree: dict[str, Any], python_structure: dict[str, Any]
) -> dict[str, Any]:
    root = Path(str(tree.get("root") or python_structure.get("root") or ""))
    candidates: dict[str, dict[str, Any]] = {}
    for rel_path in _candidate_paths(extractor, tree, python_structure):
        path = root / rel_path
        if not path.is_file() or path.stat().st_size > int(extractor.get("max_file_size_bytes") or 120_000):
            continue
        for line_no, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), start=1):
            lowered = line.lower()
            if not _has_any_marker(lowered, extractor.get("line_markers_any", [])):
                continue
            for value in _values_from_line(line, extractor):
                row = candidates.setdefault(value, {str(extractor.get("result_field") or "value"): value, "evidence": [], "score": 0})
                row["evidence"].append({"path": rel_path, "line": line_no, "text": line.strip()[:160]})
                row["score"] += _line_score(lowered, extractor)
    if not candidates:
        return dict(extractor.get("not_found") or {"status": "not_found", "evidence": []})
    result_field = str(extractor.get("result_field") or "value")
    best = sorted(candidates.values(), key=lambda row: (-int(row["score"]), str(row[result_field])))[0]
    value = best[result_field]
    if extractor.get("value_type") == "integer":
        value = int(value)
    return {
        "status": str(dict(extractor.get("found") or {}).get("status") or "found"),
        result_field: value,
        "confidence": _confidence(best, extractor),
        "evidence": best["evidence"][:5],
    }


def _candidate_paths(extractor: dict[str, Any], tree: dict[str, Any], python_structure: dict[str, Any]) -> list[str]:
    suffixes = tuple(str(item).lower() for item in extractor.get("path_suffixes", []))
    paths = []
    for item in tree.get("files", []):
        if not isinstance(item, dict):
            continue
        path = str(item.get("path") or "")
        if not suffixes or path.lower().endswith(suffixes):
            paths.append(path)
    paths.extend(str(item.get("path") or "") for item in python_structure.get("files", []) if isinstance(item, dict))
    priority = [str(item).lower() for item in extractor.get("priority_path_contains", [])]
    limit = int(extractor.get("max_files") or 80)
    return sorted(set(paths), key=lambda path: (0 if any(token in path.lower() for token in priority) else 1, path.lower()))[
        :limit
    ]


def _values_from_line(line: str, extractor: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for pattern in extractor.get("regexes", []):
        values.extend(re.findall(str(pattern), line, flags=re.IGNORECASE))
    if extractor.get("value_type") == "integer":
        values = [value for value in values if _valid_integer(value, extractor)]
    return values


def _valid_integer(value: str, extractor: dict[str, Any]) -> bool:
    try:
        number = int(value)
    except ValueError:
        return False
    bounds = extractor.get("valid_integer_range") or []
    if not isinstance(bounds, list) or len(bounds) != 2:
        return True
    return int(bounds[0]) <= number <= int(bounds[1])


def _line_score(lowered: str, extractor: dict[str, Any]) -> int:
    score = 1
    for item in extractor.get("score_markers", []):
        if not isinstance(item, dict):
            continue
        markers = [str(marker).lower() for marker in item.get("markers", [])]
        if any(marker in lowered for marker in markers):
            score += int(item.get("score") or 0)
    return score


def _confidence(row: dict[str, Any], extractor: dict[str, Any]) -> str:
    high_at = int(dict(extractor.get("found") or {}).get("confidence_score_high_at") or 4)
    return "high" if int(row.get("score") or 0) >= high_at else "medium"


def _has_any_marker(lowered: str, markers: Any) -> bool:
    return any(str(marker).lower() in lowered for marker in markers or [])
