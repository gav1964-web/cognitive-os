from __future__ import annotations

import ast
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

def _target_architecture_sketch(answers: dict[str, Any]) -> list[str]:
    scope = dict(answers.get("1_scope", {}))
    execution = dict(answers.get("2_execution", {}))
    readiness = dict(answers.get("6_runtime_extraction_readiness", {}))
    rows: list[str] = []

    entrypoints = _strings(execution.get("entrypoints"))
    if entrypoints:
        rows.append("Оставить entrypoints тонкими: " + ", ".join(entrypoints[:4]) + ".")

    scenarios = " ".join(_strings(scope.get("supported_scenarios"))).lower()
    if "http" in scenarios or execution.get("primary_execution_path"):
        rows.append("Вынести route handlers в API/web boundary layer: там валидировать запросы и делегировать работу ниже.")

    hidden = _target_refs(readiness.get("hidden_orchestrators", []))
    if hidden:
        rows.append("Вынести оркестрацию из крупных handlers в application services: " + ", ".join(hidden[:4]) + ".")

    lifecycle = readiness.get("data_lifecycle", [])
    if isinstance(lifecycle, list) and lifecycle:
        stages = [str(row.get("stage")) for row in lifecycle if isinstance(row, dict) and row.get("stage")]
        if stages:
            rows.append("Сделать жизненный цикл данных явным: " + " -> ".join(stages[:5]) + ".")

    process_boundaries = _target_refs(readiness.get("process_boundary_candidates", []))
    if process_boundaries:
        rows.append("Закрыть subprocess/network/filesystem-границы адаптерами с timeout и failure packets.")

    state = readiness.get("long_lived_state", [])
    if isinstance(state, list) and state:
        kinds = [str(row.get("kind")) for row in state if isinstance(row, dict) and row.get("kind")]
        if kinds:
            rows.append("Определить владельцев состояния и checkpoints для: " + ", ".join(dict.fromkeys(kinds[:5])) + ".")

    capabilities = _target_refs(
        dict(readiness.get("minimal_extraction_plan", {})).get("capabilities_to_extract", []),
        key="capability",
    )
    if capabilities:
        rows.append("Первыми выделять reusable pure/core capabilities: " + ", ".join(capabilities[:4]) + ".")

    return [f"- {row}" for row in rows] or ["- No target architecture sketch available."]

def _target_refs(rows: object, *, key: str | None = None) -> list[str]:
    if not isinstance(rows, list):
        return []
    refs: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        if key and row.get(key):
            refs.append(str(row.get(key)))
            continue
        path = row.get("path")
        name = row.get("name")
        target = row.get("target")
        if path and name:
            refs.append(f"{path}:{name}")
        elif target:
            refs.append(str(target))
    return refs

def _strings(value: object) -> list[str]:
    if isinstance(value, list):
        return [_value(item) for item in value if _value(item) != "n/a"]
    if value in (None, "", []):
        return []
    return [_value(value)]

def _risk_description(row: dict[str, Any]) -> str:
    value = row.get("description")
    if isinstance(value, str) and value.startswith("{"):
        try:
            value = ast.literal_eval(value)
        except (SyntaxError, ValueError):
            pass
    if isinstance(value, dict):
        code = _ru_text(value.get("code"))
        detail = _ru_text(value.get("detail"))
        severity = _ru_text(value.get("severity"))
        return f"{code}; detail: {detail}; source severity: {severity}"
    return _ru_text(value)

def _risk_mitigation(row: dict[str, Any]) -> str:
    mitigation = _ru_text(row.get("mitigation"))
    if mitigation != "n/a":
        return mitigation
    value = row.get("description")
    if isinstance(value, str) and value.startswith("{"):
        try:
            value = ast.literal_eval(value)
        except (SyntaxError, ValueError):
            pass
    code = value.get("code") if isinstance(value, dict) else None
    if code == "risky_imports":
        return "Проверить необходимость risky imports и обернуть опасные boundary в adapter/quarantine policy."
    if code == "unpinned_dependencies":
        return "Зафиксировать версии зависимостей или явно описать dependency drift policy."
    if code == "no_runtime_scripts":
        return "Добавить явную команду запуска/проверки или зафиксировать, что проект является library-only."
    return "Нужна явная митигация перед promotion."

def _source_ref(row: dict[str, Any]) -> str:
    path = row.get("path")
    name = row.get("name")
    if path and name:
        return f"{path}:{name}"
    return _value(row.get("target") or row.get("source") or row)

def _refs_line(rows: object, *, key: str | None = None) -> str:
    refs = _target_refs(rows, key=key)
    return ", ".join(refs[:6]) if refs else "не выявлено"

def _compact_dict_list(value: object, key: str) -> str:
    if not isinstance(value, dict):
        return "n/a"
    return _ru_join(value.get(key))

def _test_surface(value: object) -> str:
    if not isinstance(value, dict):
        return "n/a"
    files = value.get("test_files")
    funcs = value.get("test_functions")
    seen = value.get("python_files_seen")
    return f"test files: {_value(files)}, test functions: {_value(funcs)}, Python files seen: {_value(seen)}"

def _ru_join(value: object, *, sep: str = ", ") -> str:
    if value in (None, "", []):
        return "n/a"
    if isinstance(value, list):
        return sep.join(_ru_text(item) for item in value[:8])
    return _ru_text(value)

def _ru_text(value: object) -> str:
    text = _value(value)
    replacements = {
        "n/a": "n/a",
        "Prepare ADR and TechnicalSpec": "Подготовить ADR и техническое задание",
        "Prepare ADR and TechnicalSpec for first safe transformation": "Подготовить ADR и ТЗ для первого безопасного преобразования",
        "Extract the safest focused capability first.": "Сначала выделить самый безопасный ограниченный capability.",
        "Prepare one implementable capability extraction spec.": "Подготовить реализуемое ТЗ на выделение одного capability.",
        "Extract the safest focused capability first": "Сначала выделить самый безопасный ограниченный capability",
        "Prepare one implementable capability extraction spec": "Подготовить реализуемое ТЗ на выделение одного capability",
        "minimal_safe_extraction": "минимальное безопасное выделение",
        "Extract the safest focused capability first": "Сначала выделить самый безопасный ограниченный capability",
        "Extract capability": "Выделить capability",
        "highest fit-to-risk score for a bounded first transformation step": "лучшее соотношение пользы и риска для первого ограниченного шага",
        "domain flow anchor": "опорная функция доменного потока",
        "central flow or subsystem-level capability": "центральный узел потока или subsystem-level capability",
        "candidate": "кандидат",
        "write TechnicalSpec before Foundry build": "сначала подготовить TechnicalSpec, потом Foundry build",
        "Capability candidate requires TechnicalSpec.": "Кандидату нужен TechnicalSpec.",
        "Risk must be addressed or accepted before promotion.": "Риск нужно устранить или явно принять до promotion.",
        "Expose an HTTP API service and return structured JSON responses.": "Предоставляет HTTP API и возвращает структурированные JSON-ответы.",
        "Serve HTTP API/web requests across 8 detected routes.": "Обслуживает HTTP/API-запросы по 8 найденным routes.",
        "Handle chat/completion API requests.": "Обрабатывает chat/completion API-запросы.",
        "HTTP requests": "HTTP-запросы",
        "files or structured documents": "файлы или структурированные документы",
        "external API responses": "ответы внешних API",
        "HTTP/API responses": "HTTP/API-ответы",
        "files or serialized artifacts": "файлы или сериализованные артефакты",
        "HTTP request": "HTTP-запрос",
        "framework router": "framework router",
        "route handler": "route handler",
        "domain/provider functions": "доменные/provider-функции",
        "JSON/HTTP response": "JSON/HTTP-ответ",
        "validate request": "валидация запроса",
        "load config/state": "загрузка config/state",
        "call handler/core logic": "вызов handler/core logic",
        "handle errors": "обработка ошибок",
        "return response": "возврат ответа",
        "validate request, load config/state, call handler/core logic, handle errors, return response": (
            "валидация запроса -> загрузка config/state -> вызов handler/core logic -> обработка ошибок -> возврат ответа"
        ),
        "risky_imports": "рискованные импорты",
        "unpinned_dependencies": "незафиксированные зависимости",
        "no_runtime_scripts": "нет явных runtime-команд",
        "os, subprocess, threading": "os, subprocess, threading",
        "requirements are not fully pinned": "requirements не полностью pinned",
        "no scripts detected": "скрипты запуска не обнаружены",
        "medium": "средняя",
        "low": "низкая",
    }
    if text in replacements:
        return replacements[text]
    if "broad function can anchor a meaningful first slice" in text:
        return (
            "функция достаточно крупная, чтобы стать осмысленным первым срезом; "
            "нет заявленных side effects; контракт входа/выхода выводится из сигнатуры; "
            "есть source-backed snippet; граница выглядит полезной для архитектуры"
        )
    return text

def _table(headers: list[str], rows: list[list[object]]) -> list[str]:
    if not rows:
        return ["- Данные не записаны."]
    result = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    for row in rows[:12]:
        result.append("| " + " | ".join(_cell(value) for value in row) + " |")
    return result

def _bullet(values: object) -> list[str]:
    if not isinstance(values, list):
        values = list(values) if values else []
    rows = [f"- {_value(value)}" for value in values if _value(value) != "n/a"]
    return rows or ["- Не записано."]

def _next_step(architecture_decision: dict[str, Any], technical_spec: dict[str, Any]) -> str:
    if technical_spec.get("artifact_type") == "TechnicalSpec":
        contract = dict(technical_spec.get("extraction_contract", {}))
        return f"Передать `{_value(contract.get('candidate'))}` в Implementer можно только после человеческой проверки этого документа."
    next_artifact = dict(architecture_decision.get("next_artifact", {}))
    return f"Подготовить `{_value(next_artifact.get('type'))}` через роль {_value(next_artifact.get('recommended_role'))}."

def _cell(value: object) -> str:
    return _value(value).replace("|", "\\|").replace("\n", " ")

def _value(value: object) -> str:
    if value in (None, "", []):
        return "n/a"
    if isinstance(value, list):
        return ", ".join(_value(item) for item in value[:6])
    if isinstance(value, dict):
        return ", ".join(f"{key}={_value(item)}" for key, item in list(value.items())[:6])
    return str(value)
