"""Answer simple factual questions from Project Analyzer evidence."""

from __future__ import annotations

from typing import Any

from .code_fact_analyzers import code_fact_answers
from .import_fact_extractors import import_fact_answers
from .query_spec import query_answers, selected_query_answer
from .symbol_query import selected_symbol_query_answer, symbol_query_answers
from .text_fact_extractors import text_fact_answers
from runtime.project_fact_rules import answer_key_for_question


def run(payload: dict[str, object]) -> dict[str, object]:
    tree = dict(payload["tree"])  # type: ignore[index]
    python_structure = dict(payload["python_structure"])  # type: ignore[index]
    project_map_report = dict(payload.get("project_map_report") or {})
    scope = str(payload.get("scope") or "all")
    questions = [str(item) for item in payload.get("questions", [])]
    allowed_paths = _allowed_paths(project_map_report, scope)
    file_rows = _filter_rows(_file_rows(tree), allowed_paths)
    answers = code_fact_answers(tree, python_structure)
    answers.update(import_fact_answers(python_structure, allowed_paths))
    answers.update(text_fact_answers(tree, python_structure))
    answers.update(query_answers(questions, file_rows))
    answers.update(symbol_query_answers(questions, python_structure))
    return {
        "artifact_type": "ProjectFactQuestionAnswers",
        "scope": scope if allowed_paths is not None else "all",
        "answers": answers,
        "selected_answers": _selected_answers(questions, answers),
        "evidence_policy": "static Project Analyzer evidence plus declarative ProjectFactQuerySpec execution; no LLM inference",
    }


def _selected_answers(questions: list[str], answers: dict[str, Any]) -> list[dict[str, Any]]:
    selected = []
    for question in questions:
        query_answer = selected_query_answer(question, answers)
        if query_answer is not None:
            answer_key, answer = query_answer
            selected.append({"question": question, "answer_key": answer_key, "answer": answer})
            continue
        symbol_answer = selected_symbol_query_answer(question, answers)
        if symbol_answer is not None:
            answer_key, answer = symbol_answer
            selected.append({"question": question, "answer_key": answer_key, "answer": answer})
            continue
        answer_key = answer_key_for_question(question)
        if answer_key and answer_key in answers:
            selected.append({"question": question, "answer_key": answer_key, "answer": answers[answer_key]})
    return selected


def _file_rows(tree: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for item in tree.get("files", []):
        if not isinstance(item, dict):
            continue
        path = str(item.get("path") or "")
        if not path:
            continue
        rows.append(
            {
                "path": path,
                "extension": str(item.get("extension") or ""),
                "size_bytes": int(item.get("size_bytes") or 0),
                "line_count": int(item.get("line_count") or 0),
            }
        )
    return rows


def _allowed_paths(project_map_report: dict[str, Any], scope: str) -> set[str] | None:
    if scope != "active_core":
        return None
    answers = dict(project_map_report.get("answers") or {})
    readiness = dict(answers.get("6_runtime_extraction_readiness") or {})
    strata = dict(readiness.get("source_strata") or {})
    rows = strata.get("active_core") or []
    paths = {str(row.get("path") or "") for row in rows if isinstance(row, dict) and row.get("path")}
    return paths or None


def _filter_rows(rows: list[dict[str, Any]], allowed_paths: set[str] | None) -> list[dict[str, Any]]:
    if allowed_paths is None:
        return rows
    return [row for row in rows if str(row.get("path") or "") in allowed_paths]
