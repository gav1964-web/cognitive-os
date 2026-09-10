"""Config-driven symbol queries over extracted Python structure."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
PATTERNS_PATH = ROOT / "config" / "project_symbol_query_patterns.json"


def symbol_query_answers(questions: list[str], python_structure: dict[str, Any]) -> dict[str, dict[str, Any]]:
    payload = load_symbol_query_patterns()
    symbols = _function_symbols(python_structure)
    answers: dict[str, dict[str, Any]] = {}
    for question in questions:
        spec = parse_symbol_query_spec(question, patterns=payload)
        if spec is None:
            continue
        answers[str(spec["answer_key"])] = execute_symbol_query_spec(spec, symbols)
    return answers


def selected_symbol_query_answer(question: str, answers: dict[str, Any]) -> tuple[str, dict[str, Any]] | None:
    spec = parse_symbol_query_spec(question)
    if spec is None:
        return None
    answer_key = str(spec["answer_key"])
    answer = answers.get(answer_key)
    if isinstance(answer, dict):
        return answer_key, answer
    return None


def parse_symbol_query_spec(question: str, *, patterns: dict[str, Any] | None = None) -> dict[str, Any] | None:
    payload = patterns or load_symbol_query_patterns()
    lowered = question.lower()
    for pattern in payload.get("patterns", []):
        if not isinstance(pattern, dict) or not _matches_pattern(lowered, pattern):
            continue
        facts = _extract_facts(question, lowered, pattern)
        spec = _build_spec(pattern, facts)
        if spec is not None:
            spec["include_purpose_summary"] = _wants_purpose_summary(lowered, payload)
            spec["wants_repeated_reason"] = _wants_repeated_reason(lowered, payload)
            return spec
    return None


def execute_symbol_query_spec(spec: dict[str, Any], symbols: list[dict[str, Any]]) -> dict[str, Any]:
    rows = list(symbols)
    for flt in spec.get("filters", []):
        if isinstance(flt, dict):
            rows = [row for row in rows if _matches_filter(row, flt)]
    grouped = _group_by_path(rows, spec)
    for sort in reversed([row for row in spec.get("sort", []) if isinstance(row, dict)]):
        field = str(sort.get("field") or "path")
        reverse = str(sort.get("direction") or "asc") == "desc"
        grouped.sort(key=lambda row: row.get(field), reverse=reverse)
    output_fields = [str(field) for field in spec.get("output_fields", []) if field]
    files = [{field: row.get(field) for field in output_fields} for row in grouped]
    return {
        "artifact_type": "ProjectSymbolQueryResult",
        "query_spec": spec,
        "count": len(files),
        "count_total": len(rows),
        "count_files": len(files),
        "files": files,
        "rows": rows,
    }


def load_symbol_query_patterns() -> dict[str, Any]:
    payload = json.loads(PATTERNS_PATH.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "project_symbol_query_patterns.v1":
        raise ValueError("project symbol query patterns schema mismatch")
    if payload.get("status") != "active":
        raise ValueError("project symbol query patterns must be active")
    return payload


def _function_symbols(python_structure: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    root = str(python_structure.get("root") or "")
    for file_row in python_structure.get("files", []):
        if not isinstance(file_row, dict):
            continue
        path = str(file_row.get("path") or "")
        for function in file_row.get("functions", []):
            if not isinstance(function, dict):
                continue
            rows.append(
                {
                    "path": path or str(function.get("path") or ""),
                    "name": str(function.get("name") or ""),
                    "line": int(function.get("line") or 0),
                    "end_line": int(function.get("end_line") or 0),
                    "loc": int(function.get("loc") or 0),
                    "root": root,
                    "args": list(function.get("args") or []),
                    "returns": str(function.get("returns") or ""),
                    "calls": list(function.get("calls") or []),
                    "side_effects": list(function.get("side_effects") or []),
                    "decorators": list(function.get("decorators") or []),
                    "docstring": bool(function.get("docstring")),
                }
            )
    return rows


def _matches_pattern(lowered: str, pattern: dict[str, Any]) -> bool:
    for group in pattern.get("all_markers", []):
        if not isinstance(group, list):
            return False
        if not any(str(marker).lower() in lowered for marker in group):
            return False
    return True


def _extract_facts(question: str, lowered: str, pattern: dict[str, Any]) -> dict[str, str]:
    facts: dict[str, str] = {}
    token = _token_after_marker(question, lowered, [str(item) for item in pattern.get("token_after_markers", [])])
    if token:
        facts.update({"query_token": token, "query_token_slug": _slug(token)})
    function_name = _token_after_marker(question, lowered, [str(item) for item in pattern.get("function_after_markers", [])])
    if function_name:
        facts.update({"function_name": function_name, "function_name_slug": _slug(function_name)})
    call_target = _call_after_marker(question, [str(item) for item in pattern.get("call_after_markers", [])])
    if call_target:
        facts.update({"call_target": call_target, "call_target_slug": _slug(call_target)})
    source_path = _path_after_marker(question, [str(item) for item in pattern.get("path_after_markers", [])])
    if source_path:
        facts.update({"source_path": source_path, "source_path_slug": _slug(source_path)})
    return facts


def _token_after_marker(question: str, lowered: str, markers: list[str]) -> str:
    for marker in markers:
        match = re.search(rf"{re.escape(marker)}\s+([A-Za-zА-Яа-я0-9_]+)", lowered, flags=re.IGNORECASE)
        if match:
            return match.group(1)
    quoted = re.search(r"[\"'`](.+?)[\"'`]", question)
    if quoted:
        return quoted.group(1).strip()
    return ""


def _build_spec(pattern: dict[str, Any], facts: dict[str, str]) -> dict[str, Any] | None:
    filters = []
    for flt in pattern.get("filters", []):
        if not isinstance(flt, dict):
            continue
        resolved = dict(flt)
        if "value_from" in resolved:
            value = facts.get(str(resolved.pop("value_from")))
            if not value:
                return None
            resolved["value"] = value
        filters.append(resolved)
    return {
        "artifact_type": "ProjectSymbolQuerySpec",
        "pattern_id": pattern.get("id"),
        "target": pattern.get("target"),
        "filters": filters,
        "group_by": pattern.get("group_by"),
        "sort": list(pattern.get("sort", [])),
        "output_fields": list(pattern.get("output_fields", [])),
        "row_fields": list(pattern.get("row_fields", [])),
        "include_source": bool(pattern.get("include_source")),
        "include_call_explanation": bool(pattern.get("include_call_explanation")),
        "max_source_lines": int(pattern.get("max_source_lines") or 220),
        **{key: value for key, value in facts.items() if key in {"query_token", "function_name", "source_path", "call_target"}},
        "answer_key": str(pattern.get("answer_key_template") or pattern.get("id")).format(**facts),
    }


def _matches_filter(row: dict[str, Any], flt: dict[str, Any]) -> bool:
    field = str(flt.get("field") or "")
    op = str(flt.get("op") or "")
    expected = str(flt.get("value") or "")
    actual = str(row.get(field) or "")
    if op == "contains_ci":
        return expected.lower() in actual.lower()
    if op == "contains":
        return expected in actual
    if op == "eq":
        return actual == expected
    if op == "path_eq":
        return _normalize_path(actual) == _normalize_path(expected)
    return False


def _group_by_path(rows: list[dict[str, Any]], spec: dict[str, Any]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    row_fields = [str(field) for field in spec.get("row_fields", [])]
    include_summary = bool(spec.get("include_purpose_summary"))
    summary_config = dict(load_symbol_query_patterns().get("purpose_summary") or {})
    for row in rows:
        function_row = {field: row.get(field) for field in row_fields}
        if spec.get("include_source") and "source" in row_fields:
            function_row["source"] = _source_snippet(row, int(spec.get("max_source_lines") or 220))
        if spec.get("include_call_explanation") and "call_explanation" in row_fields:
            function_row["call_explanation"] = _call_explanation(row, spec, summary_config)
        if include_summary:
            function_row["purpose_summary"] = _purpose_summary(row, summary_config)
        grouped.setdefault(str(row.get("path") or ""), []).append(function_row)
    return [
        {"path": path, "functions": sorted(functions, key=lambda item: (int(item.get("line") or 0), str(item.get("name") or "")))}
        for path, functions in grouped.items()
    ]


def _slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9А-Яа-я]+", "_", value).strip("_").lower()


def _wants_purpose_summary(lowered: str, payload: dict[str, Any]) -> bool:
    config = dict(payload.get("purpose_summary") or {})
    return any(str(marker).lower() in lowered for marker in config.get("trigger_markers", []))


def _wants_repeated_reason(lowered: str, payload: dict[str, Any]) -> bool:
    config = dict(payload.get("call_explanation") or {})
    return any(str(marker).lower() in lowered for marker in config.get("why_repeated_markers", []))


def _purpose_summary(row: dict[str, Any], summary_config: dict[str, Any]) -> str:
    name = str(row.get("name") or "")
    tokens = _name_tokens(name)
    hints = dict(summary_config.get("token_hints") or {})
    matched_hints = []
    for token in tokens:
        hint = hints.get(token.lower())
        if hint and hint not in matched_hints:
            matched_hints.append(str(hint))
    if matched_hints:
        base = "; ".join(matched_hints[:3])
    else:
        base = "назначение выводится по имени функции и AST-фактам"
    details = []
    calls = [str(item) for item in row.get("calls", []) if item]
    if calls:
        details.append(f"вызывает: {', '.join(calls[: int(summary_config.get('max_call_examples') or 4)])}")
    effects = [str(item) for item in row.get("side_effects", []) if item]
    if effects:
        details.append(f"side effects: {', '.join(effects)}")
    returns = str(row.get("returns") or "")
    if returns:
        details.append(f"returns: {returns}")
    if row.get("docstring"):
        details.append("есть docstring")
    suffix = f" ({'; '.join(details)})" if details else ""
    return f"{name}: {base}{suffix}."


def _name_tokens(name: str) -> list[str]:
    snake_parts = re.split(r"[_\\W]+", name)
    tokens = []
    for part in snake_parts:
        if not part:
            continue
        tokens.extend(re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?=[A-Z]|$)|\\d+", part) or [part])
    return [token.lower() for token in tokens if token]


def _call_after_marker(question: str, markers: list[str]) -> str:
    for marker in markers:
        match = re.search(rf"{re.escape(marker)}\s+([A-Za-z_][A-Za-z0-9_.]*)(?:\s*\()?", question, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip().rstrip("(")
    return ""


def _path_after_marker(question: str, markers: list[str]) -> str:
    for marker in markers:
        match = re.search(rf"{re.escape(marker)}\s+([A-Za-z0-9_./\\\\-]+\.py)", question, flags=re.IGNORECASE)
        if match:
            return _normalize_path(match.group(1))
    return ""


def _normalize_path(value: str) -> str:
    return value.replace("\\", "/").strip().lstrip("./")


def _source_snippet(row: dict[str, Any], max_source_lines: int) -> dict[str, Any]:
    root = Path(str(row.get("root") or ""))
    rel_path = _normalize_path(str(row.get("path") or ""))
    start = int(row.get("line") or 0)
    end = int(row.get("end_line") or 0)
    if not root or not rel_path or start <= 0:
        return {"status": "not_available", "reason": "missing root/path/line"}
    path = root / rel_path
    if not path.is_file():
        return {"status": "not_found", "path": rel_path}
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    if end <= 0:
        end = min(len(lines), start + max(0, int(row.get("loc") or 1)) - 1)
    end = min(end, start + max_source_lines - 1, len(lines))
    return {
        "status": "found",
        "path": rel_path,
        "start_line": start,
        "end_line": end,
        "text": "\n".join(lines[start - 1 : end]),
        "truncated": end < int(row.get("end_line") or end),
    }


def _call_explanation(row: dict[str, Any], spec: dict[str, Any], summary_config: dict[str, Any]) -> dict[str, Any]:
    call_target = str(spec.get("call_target") or "")
    source = _source_snippet(row, int(spec.get("max_source_lines") or 220))
    occurrences = []
    if source.get("status") == "found":
        for offset, line in enumerate(str(source.get("text") or "").splitlines(), start=int(source.get("start_line") or 1)):
            if call_target in line:
                occurrences.append({"line": offset, "text": line.strip()})
    config = dict(load_symbol_query_patterns().get("call_explanation") or {})
    hints = dict(config.get("call_hints") or {})
    hint = dict(hints.get(call_target) or {})
    return {
        "call_target": call_target,
        "occurrence_count": len(occurrences),
        "occurrences": occurrences,
        "summary": hint.get("summary") or "назначение вызова выводится по имени и строкам использования",
        "why_repeated": _why_repeated(call_target, occurrences, hint, bool(spec.get("wants_repeated_reason"))),
        "source_status": source.get("status"),
    }


def _why_repeated(call_target: str, occurrences: list[dict[str, Any]], hint: dict[str, Any], wants_reason: bool) -> str:
    if not wants_reason:
        return ""
    if len(occurrences) <= 1:
        return "в найденной функции этот вызов не повторяется"
    assigned_names = [_first_string_argument(str(item.get("text") or "")) for item in occurrences]
    assigned_names = [name for name in assigned_names if name]
    base = str(hint.get("typical_reason_repeated") or "повтор используется для нескольких независимых действий")
    if assigned_names:
        return f"{base}: {', '.join(assigned_names)}"
    return base


def _first_string_argument(line: str) -> str:
    match = re.search(r"\(\s*[\"']([^\"']+)[\"']", line)
    return match.group(1) if match else ""
