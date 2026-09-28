"""Config-driven source-code fact analyzers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from runtime.project_fact_rules import matches_line


ROOT = Path(__file__).resolve().parents[3]
ANALYZERS_PATH = ROOT / "config" / "project_code_fact_analyzers.json"


def code_fact_answers(tree: dict[str, Any], python_structure: dict[str, Any]) -> dict[str, dict[str, Any]]:
    payload = load_code_fact_analyzers()
    answers: dict[str, dict[str, Any]] = {}
    for analyzer in payload.get("analyzers", []):
        if not isinstance(analyzer, dict):
            continue
        answer_key = str(analyzer.get("answer_key") or "")
        answers[answer_key] = _run_analyzer(analyzer, tree, python_structure)
    for derived in payload.get("derived_answers", []):
        if not isinstance(derived, dict):
            continue
        answer_key = str(derived.get("answer_key") or "")
        answers[answer_key] = _run_derived_answer(derived, answers)
    return answers


def load_code_fact_analyzers() -> dict[str, Any]:
    payload = json.loads(ANALYZERS_PATH.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "project_code_fact_analyzers.v1":
        raise ValueError("project code fact analyzers schema mismatch")
    if payload.get("status") != "active":
        raise ValueError("project code fact analyzers must be active")
    return payload


def _run_analyzer(analyzer: dict[str, Any], tree: dict[str, Any], python_structure: dict[str, Any]) -> dict[str, Any]:
    signals = _collect_signals(analyzer, tree, python_structure)
    matched = {name for name, rows in signals.items() if rows}
    for case in analyzer.get("cases", []):
        if isinstance(case, dict) and _case_matches(case, matched):
            result = dict(case.get("result") or {})
            result["evidence"] = _evidence_for_case(case, signals)
            return result
    result = dict(analyzer.get("default_result") or {"status": "not_found", "evidence": []})
    result["evidence"] = []
    return result


def _collect_signals(
    analyzer: dict[str, Any], tree: dict[str, Any], python_structure: dict[str, Any]
) -> dict[str, list[dict[str, Any]]]:
    root = Path(str(tree.get("root") or python_structure.get("root") or ""))
    signals = {str(name): [] for name in dict(analyzer.get("signals") or {})}
    for rel_path in _candidate_paths(analyzer, tree, python_structure):
        path = root / rel_path
        if not path.is_file() or path.stat().st_size > int(analyzer.get("max_file_size_bytes") or 160_000):
            continue
        for line_no, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), start=1):
            for signal_name, signal_rule in dict(analyzer.get("signals") or {}).items():
                if isinstance(signal_rule, dict) and _line_matches_signal(line, signal_rule):
                    signals[str(signal_name)].append({"path": rel_path, "line": line_no, "text": line.strip()[:180]})
    return signals


def _candidate_paths(analyzer: dict[str, Any], tree: dict[str, Any], python_structure: dict[str, Any]) -> list[str]:
    paths = []
    contains = [str(item).lower() for item in analyzer.get("path_contains", [])]
    suffixes = tuple(str(item).lower() for item in analyzer.get("path_suffixes", []))
    exact_paths = {str(item).lower() for item in analyzer.get("exact_paths", [])}
    py_only = bool(analyzer.get("python_only"))
    for item in tree.get("files", []):
        if not isinstance(item, dict):
            continue
        path = str(item.get("path") or "")
        lower = path.lower()
        if _excluded(lower, analyzer) or (py_only and not lower.endswith(".py")):
            continue
        if any(token in lower for token in contains) or lower.endswith(suffixes) or lower in exact_paths:
            paths.append(path)
    py_contains = [str(item).lower() for item in analyzer.get("python_structure_path_contains", [])]
    paths.extend(
        str(item.get("path") or "")
        for item in python_structure.get("files", [])
        if isinstance(item, dict) and _python_structure_path_matches(str(item.get("path") or ""), py_contains, analyzer)
    )
    limit = int(analyzer.get("max_files") or 80)
    return sorted(set(paths), key=lambda path: path.lower())[:limit]


def _python_structure_path_matches(path: str, contains: list[str], analyzer: dict[str, Any]) -> bool:
    lower = path.lower()
    if _excluded(lower, analyzer):
        return False
    if bool(analyzer.get("python_only")) and not lower.endswith(".py"):
        return False
    return any(token in lower for token in contains)


def _excluded(lower: str, analyzer: dict[str, Any]) -> bool:
    return bool(analyzer.get("exclude_tests")) and (
        lower.startswith(("tests/", "test/")) or "/tests/" in lower or "/test/" in lower
    )


def _line_matches_signal(line: str, signal_rule: dict[str, Any]) -> bool:
    return matches_line(
        line,
        any_markers=[str(item) for item in signal_rule.get("any_markers", [])],
        all_groups=[[str(item) for item in group] for group in signal_rule.get("all_groups", [])],
    )


def _case_matches(case: dict[str, Any], matched: set[str]) -> bool:
    all_required = {str(item) for item in case.get("if_signals_all", [])}
    any_required = {str(item) for item in case.get("if_signals_any", [])}
    return all_required <= matched and (not any_required or bool(any_required & matched))


def _evidence_for_case(case: dict[str, Any], signals: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    rows = []
    for name in case.get("evidence_signals", []):
        rows.extend(signals.get(str(name), [])[:4])
    return _dedupe_evidence(rows)[: int(case.get("evidence_limit") or 10)]


def _run_derived_answer(derived: dict[str, Any], answers: dict[str, dict[str, Any]]) -> dict[str, Any]:
    dependency = answers.get(str(derived.get("depends_on") or ""), {})
    template_key = "positive" if dependency.get("status") == derived.get("if_dependency_status") else "fallback"
    result = dict(derived.get(template_key) or {})
    result["evidence"] = list(dependency.get("evidence") or [])
    return result


def _dedupe_evidence(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, int]] = set()
    result = []
    for row in rows:
        key = (str(row.get("path") or ""), int(row.get("line") or 0))
        if key in seen:
            continue
        seen.add(key)
        result.append(row)
    return result
