"""Generated L4.5 semantic benchmark corpus."""

from __future__ import annotations

import random
from typing import Any


KNOWN_TEMPLATES = {
    "csv_sort_cli": "Напиши CLI-утилиту без внешних зависимостей, которая читает CSV-файл, сортирует строки по колонке name, сохраняет CSV-файл, имеет README и тесты.",
    "text_stats_cli": "Напиши CLI-утилиту без внешних зависимостей, которая читает текстовый файл, считает строки, слова и символы, сохраняет JSON-отчёт, имеет README и тесты.",
    "json_log_filter_cli": "Напиши CLI-утилиту без внешних зависимостей, которая читает JSONL-файл логов, фильтрует записи уровня ERROR, пропускает malformed строки, сохраняет новый JSONL-файл, имеет README и тесты.",
    "fastapi_kv_store": "Сделай локальную FastAPI-службу с зависимостью fastapi, которая реализует key-value CRUD API, хранит данные в памяти, возвращает JSON, имеет controlled 404, README, тесты и команду запуска.",
}

UNKNOWN_CLI_TASKS = [
    ("csv_normalize", "читает CSV-файл, нормализует значения в колонке name, сохраняет CSV-файл"),
    ("csv_deduplicate", "читает CSV-файл, удаляет дубликаты по колонке email, сохраняет CSV-файл"),
    ("json_validate", "читает JSON-файл, валидирует обязательные поля id/name, сохраняет JSON-отчёт"),
    ("markdown_links", "читает markdown-файл, извлекает ссылки, сохраняет JSON-отчёт"),
    ("html_title", "читает HTML-файл, извлекает title, сохраняет JSON-отчёт"),
    ("xlsx_json", "читает XLSX-файл, сохраняет JSON-отчёт"),
    ("url_status", "читает список URL из файла, проверяет HTTP status, сохраняет JSON-отчёт"),
    ("directory_manifest", "читает каталог файлов, строит JSON manifest, сохраняет JSON-отчёт"),
]

FASTAPI_UNKNOWN_TASKS = [
    ("image_metadata", "принимает JSON с именем изображения, возвращает JSON metadata report"),
    ("csv_preview", "принимает CSV payload, возвращает JSON preview первых строк"),
    ("checksum_api", "принимает JSON payload, считает checksum, возвращает JSON response"),
]

CLARIFICATION_TASKS = [
    ("vague_files", "Сделай полезную штуку для файлов."),
    ("too_broad", "Сделай любую систему для обработки всего что нужно."),
    ("secret_boundary", "Напиши CLI-утилиту с api key, которая читает URL из файла, вызывает внешний API, сохраняет JSON-отчёт, имеет README и тесты."),
    ("mobile_app", "Создай мобильное приложение с push-уведомлениями, авторизацией и публикацией в store."),
    ("blockchain", "Напиши blockchain smart contract, который принимает JSON input, возвращает transaction receipt JSON, имеет README и тесты, без внешних зависимостей."),
]

RISK_BOUNDARY_TASKS = [
    (
        "source_edit",
        "Измени исходники проекта: напиши CLI-утилиту без внешних зависимостей, которая читает JSON-файл, сохраняет JSON-отчёт, имеет README и тесты.",
        "record_template_backlog_requires_human_review",
    ),
    (
        "network_scraper",
        "Напиши CLI-скрапер с зависимостью requests, который читает URL, скачивает HTML, сохраняет JSON-отчёт, имеет README и тесты.",
        "record_template_backlog_requires_human_review",
    ),
    (
        "desktop_gui",
        "Напиши desktop GUI приложение без внешних зависимостей, которое читает CSV файл, показывает таблицу, сохраняет JSON отчет, имеет README и тесты.",
        "ask_clarification",
    ),
]

CORPUS_PROFILES = {
    "balanced": ("known", "unknown_cli", "unknown_fastapi", "clarification"),
    "risk_heavy": ("risk", "risk", "risk", "unknown_cli", "clarification"),
    "unknown_template_heavy": ("unknown_cli", "unknown_cli", "unknown_fastapi", "known"),
    "known_template_regression": ("known",),
}

def generate_l45_semantic_cases(*, size: int, seed: int = 45, profile: str = "balanced") -> list[dict[str, Any]]:
    """Generate deterministic prompt-boundary cases for broader field trials."""

    if profile not in CORPUS_PROFILES:
        raise ValueError(f"unknown L4.5 semantic corpus profile: {profile}")
    rng = random.Random(seed)
    templates = _profile_templates(profile)
    cases: list[dict[str, Any]] = []
    for index in range(size):
        template = dict(rng.choice(templates))
        case = dict(template)
        case["case_id"] = f"generated_{index + 1:03d}_{template['case_id']}"
        case["corpus_profile"] = profile
        cases.append(case)
    return cases


def _profile_templates(profile: str) -> list[dict[str, Any]]:
    groups = {
        "known": _known_cases(),
        "unknown_cli": _unknown_cli_cases(),
        "unknown_fastapi": _unknown_fastapi_cases(),
        "clarification": _clarification_cases(),
        "risk": _risk_boundary_cases(),
    }
    templates: list[dict[str, Any]] = []
    for group_name in CORPUS_PROFILES[profile]:
        templates.extend(groups[group_name])
    return templates


def _known_cases() -> list[dict[str, Any]]:
    return [
        {
            "case_id": f"known_{template_id}",
            "prompt": prompt,
            "supported_template": template_id,
            "expected_escalation": False,
            "expected_l4_action": "build_verified_system_package",
        }
        for template_id, prompt in KNOWN_TEMPLATES.items()
    ]


def _unknown_cli_cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for task_id, action in UNKNOWN_CLI_TASKS:
        dependency = "без внешних зависимостей"
        if task_id in {"url_status", "xlsx_json"}:
            dependency = "с разрешенной зависимостью requests" if task_id == "url_status" else "с зависимостью openpyxl"
        cases.append(
            {
                "case_id": f"unknown_cli_{task_id}",
                "prompt": f"Напиши CLI-утилиту {dependency}, которая {action}, имеет README и тесты.",
                "supported_template": None,
                "expected_escalation": True,
                "expected_hypothesis_type": "new_template_candidate",
                "expected_l4_action": "record_template_backlog",
            }
        )
    return cases


def _unknown_fastapi_cases() -> list[dict[str, Any]]:
    return [
        {
            "case_id": f"unknown_fastapi_{task_id}",
            "prompt": f"Сделай локальную FastAPI-службу с зависимостью fastapi, которая {action}, имеет README, тесты и команду запуска.",
            "supported_template": None,
            "expected_escalation": True,
            "expected_hypothesis_type": "new_template_candidate",
            "expected_l4_action": "record_template_backlog",
        }
        for task_id, action in FASTAPI_UNKNOWN_TASKS
    ]


def _clarification_cases() -> list[dict[str, Any]]:
    return [
        {
            "case_id": f"clarify_{task_id}",
            "prompt": prompt,
            "supported_template": None,
            "expected_escalation": False,
            "expected_l4_action": "ask_clarification",
        }
        for task_id, prompt in CLARIFICATION_TASKS
    ]


def _risk_boundary_cases() -> list[dict[str, Any]]:
    return [
        {
            "case_id": f"risk_{task_id}",
            "prompt": prompt,
            "supported_template": None,
            "expected_escalation": True,
            "expected_hypothesis_type": "new_template_candidate",
            "expected_l4_action": expected_action,
        }
        for task_id, prompt, expected_action in RISK_BOUNDARY_TASKS
    ]
