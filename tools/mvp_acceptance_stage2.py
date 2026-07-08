"""Stage 2 and programmer acceptance gates."""

from __future__ import annotations

import sys

import mvp_acceptance_programmer_checks as programmer_checks


STAGE2_PROMPT = (
    "Напиши CLI-утилиту без внешних зависимостей, которая читает JSONL-файл логов, "
    "фильтрует записи уровня ERROR, пропускает malformed строки, сохраняет новый JSONL-файл, "
    "имеет README и тесты."
)
STAGE2_FASTAPI_PROMPT = (
    "Сделай локальную FastAPI-службу с зависимостью fastapi, которая принимает CSV, "
    "валидирует колонки category/value, считает агрегаты по category, сохраняет JSON-отчёт, "
    "имеет README, тесты и команду запуска."
)
STAGE2_TEXT_STATS_PROMPT = (
    "Напиши CLI-утилиту без внешних зависимостей, которая читает текстовый файл, "
    "считает строки, слова и символы, сохраняет JSON-отчёт, имеет README и тесты."
)
STAGE2_FASTAPI_KV_PROMPT = (
    "Сделай локальную FastAPI-службу с зависимостью fastapi, которая реализует key-value CRUD API, "
    "хранит данные в памяти, возвращает JSON, имеет controlled 404 для отсутствующего ключа, "
    "README, тесты и команду запуска."
)


def stage2_checks(report) -> None:
    report.command(
        "programmer_prompt_curriculum_local_10",
        [sys.executable, "tools/programmer_prompt_curriculum.py", "--root", ".", "--curriculum-dir", "curricula/programmer_prompt_local_10", "--write"],
        layers=["L4"], check=programmer_checks.programmer_prompt_local_10_ok,
    )
    report.command(
        "programmer_project_review",
        [sys.executable, "tools/programmer_project_review.py", "--root", ".", "--case", "json_log_filter_cli", "--write"],
        layers=["L4"], check=programmer_checks.programmer_project_review_ok,
    )
    report.command(
        "verified_system_package",
        [sys.executable, "tools/verified_system_package.py", "--root", ".", "--prompt", STAGE2_PROMPT, "--write"],
        layers=["L4"], check=programmer_checks.verified_system_package_ok,
    )
    report.command(
        "verified_system_package_fastapi",
        [
            sys.executable,
            "tools/verified_system_package.py",
            "--root",
            ".",
            "--curriculum-dir",
            "curricula/programmer_prompt_stage2",
            "--prompt",
            STAGE2_FASTAPI_PROMPT,
            "--write",
        ],
        layers=["L4"], check=programmer_checks.verified_system_package_ok,
    )
    report.command(
        "verified_system_package_text_stats",
        [
            sys.executable,
            "tools/verified_system_package.py",
            "--root",
            ".",
            "--curriculum-dir",
            "curricula/programmer_prompt_stage2",
            "--prompt",
            STAGE2_TEXT_STATS_PROMPT,
            "--write",
        ],
        layers=["L4"], check=programmer_checks.verified_system_package_ok,
    )
    report.command(
        "verified_system_package_fastapi_kv",
        [
            sys.executable,
            "tools/verified_system_package.py",
            "--root",
            ".",
            "--curriculum-dir",
            "curricula/programmer_prompt_stage2",
            "--prompt",
            STAGE2_FASTAPI_KV_PROMPT,
            "--write",
        ],
        layers=["L4"], check=programmer_checks.verified_system_package_ok,
    )
