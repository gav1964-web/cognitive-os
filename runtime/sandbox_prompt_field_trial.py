"""Field trial runner for sandbox programmer prompt normalization."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .llm_sandbox_implementation import run_llm_sandbox_implementation


DEFAULT_PROMPTS = [
    "Напиши CLI .py, которая считает строки CSV файла.",
    "Нужна консольная утилита: посчитать записи в csv и сохранить число в файл.",
    "Сделай скрипт, который упорядочит csv по первому столбцу.",
    "CLI: оставь в CSV только первые две колонки.",
    "Нужен .py инструмент, который выкинет строки CSV без значения в первой колонке.",
    "Сделай маленькую утилиту: HTML-таблицу превратить в CSV.",
    "Напиши скрипт, который красиво отформатирует JSON.",
    "CLI должен достать значение первого ключа из JSON объекта.",
    "Нужен скрипт, который переведет текст в большие буквы.",
    "Сделай консольную штуку, которая уберет пробелы по краям текста.",
    "Нужна утилита, которая отсортирует строки текстового файла.",
    "Сделай CLI, который удалит повторяющиеся строки и оставит первые вхождения.",
    "Напиши программу, которая сложит значения второй колонки CSV.",
    "Нужен скрипт: превратить CSV с заголовком в JSON записи.",
    "CLI должен перечислить ключи верхнего уровня JSON объекта.",
    "Напиши CLI: из CSV убрать строки с пустой первой колонкой, оставить первые две колонки и вывести JSON.",
    "Сделай CLI: убери пробелы по краям текста и переведи в большие буквы.",
    "Напиши CLI, который скачает сайт и сделает PDF.",
    "Создай программу, которая сама выберет лучшую библиотеку и установит ее.",
]


def run_sandbox_prompt_field_trial(
    *,
    root: Path,
    prompts: list[str] | None = None,
    use_model: bool = False,
    write: bool = False,
) -> dict[str, Any]:
    rows = []
    for index, prompt in enumerate(prompts or DEFAULT_PROMPTS, start=1):
        report = run_llm_sandbox_implementation(root=root, prompt=prompt, use_model=use_model, write=write)
        resolution = dict(report.get("route_resolution") or {})
        plan = dict(report.get("implementation_plan") or {})
        operation = dict(plan.get("operation") or {})
        verification = dict(report.get("verification") or {})
        tests = dict(verification.get("tests") or {})
        rows.append(
            {
                "case_id": f"case{index:03d}",
                "prompt": prompt,
                "status": report.get("status"),
                "operation_id": operation.get("operation"),
                "profile": operation.get("profile"),
                "strategy": resolution.get("strategy"),
                "resolution_status": resolution.get("status"),
                "model_invoked": bool(resolution.get("model_invoked")),
                "confidence": resolution.get("confidence"),
                "verification_status": verification.get("status", "not_run"),
                "tests_status": tests.get("status", "not_run"),
                "reason": report.get("reason"),
                "errors": resolution.get("errors", []),
            }
        )
    return _summarize(rows=rows, use_model=use_model, write=write)


def _summarize(*, rows: list[dict[str, Any]], use_model: bool, write: bool) -> dict[str, Any]:
    sandbox_verified = sum(1 for row in rows if row["status"] == "sandbox_verified")
    blocked = sum(1 for row in rows if row["status"] == "blocked")
    planned = sum(1 for row in rows if row["status"] == "planned")
    model_invoked = sum(1 for row in rows if row["model_invoked"])
    strategy_counts: dict[str, int] = {}
    operation_counts: dict[str, int] = {}
    for row in rows:
        strategy = str(row.get("strategy") or "unknown")
        operation = str(row.get("operation_id") or "none")
        strategy_counts[strategy] = strategy_counts.get(strategy, 0) + 1
        operation_counts[operation] = operation_counts.get(operation, 0) + 1
    return {
        "artifact_type": "SandboxPromptFieldTrialReport",
        "status": "ok",
        "config": {"use_model": use_model, "write": write, "case_count": len(rows)},
        "summary": {
            "sandbox_verified": sandbox_verified,
            "planned": planned,
            "blocked": blocked,
            "model_invoked": model_invoked,
            "strategy_counts": strategy_counts,
            "operation_counts": operation_counts,
        },
        "cases": rows,
    }
