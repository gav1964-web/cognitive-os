"""Human-readable greenfield architecture and TechnicalSpec documents."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def write_product_architecture_document(*, root: Path, architecture: dict[str, Any], output_group: str = "greenfield") -> Path:
    out_dir = root / "artifacts" / "roles" / output_group
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"product_architecture_{_stamp()}.md"
    path.write_text(render_product_architecture_document(architecture), encoding="utf-8")
    return path


def write_product_technical_spec_document(*, root: Path, technical_spec: dict[str, Any], output_group: str = "greenfield") -> Path:
    out_dir = root / "artifacts" / "roles" / output_group
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"product_technical_spec_{_stamp()}.md"
    path.write_text(render_product_technical_spec_document(technical_spec), encoding="utf-8")
    return path


def render_product_architecture_document(architecture: dict[str, Any]) -> str:
    question_policy = dict(architecture.get("open_question_policy", {}))
    first_slice = _first_slice(architecture)
    return "\n".join(
        [
            "# Архитектура нового проекта",
            "",
            f"Prompt: {_value(architecture.get('prompt'))}",
            f"Тип системы: {_value(architecture.get('system_type'))}",
            f"Стиль архитектуры: {_value(architecture.get('architecture_style'))}",
            "",
            "## Кратко",
            "",
            _value(architecture.get("product_summary")),
            "",
            "## Архитектурное решение",
            "",
            _architecture_decision_text(architecture),
            "",
            "## Research Hints",
            "",
            *_table(["Тема", "Для чего", "Политика проверки", "Статус"], [[r.get("topic"), r.get("use_for"), r.get("evidence_policy"), r.get("authority")] for r in architecture.get("research_hints", [])]),
            "",
            "## Архитектурные варианты",
            "",
            *_table(["Вариант", "Статус", "Решение", "Tradeoffs"], [[r.get("id"), r.get("status"), r.get("decision"), r.get("tradeoffs")] for r in architecture.get("architecture_options", [])]),
            "",
            "## Первый полезный срез",
            "",
            *_bullet(first_slice),
            "",
            "## Основные сценарии",
            "",
            *_table(["ID", "Сценарий", "Успех"], [[r.get("id"), r.get("description"), r.get("success")] for r in architecture.get("main_scenarios", [])]),
            "",
            "## Компоненты",
            "",
            *_table(["Компонент", "Назначение", "Вход", "Выход"], [[r.get("id"), r.get("purpose"), r.get("inputs"), r.get("outputs")] for r in architecture.get("components", [])]),
            "",
            "## Внешние границы",
            "",
            *_table(["Граница", "Side effects", "Политика"], [[r.get("target"), r.get("side_effects"), r.get("policy")] for r in architecture.get("external_boundaries", [])]),
            "",
            "## Security Policy",
            "",
            *_bullet(architecture.get("security_policy", [])),
            "",
            "## Риски",
            "",
            *_table(["Severity", "Risk", "Mitigation"], [[r.get("severity"), r.get("risk"), r.get("mitigation")] for r in architecture.get("risks", [])]),
            "",
            "## Допущения до уточнения",
            "",
            *_bullet(_assumptions(architecture)),
            "",
            "## План проверки",
            "",
            *_bullet(_architecture_verification_plan(architecture)),
            "",
            "## Политика открытых вопросов",
            "",
            f"- Режим: {_value(question_policy.get('mode'))}",
            f"- Решение: {_value(question_policy.get('decision'))}",
            f"- По умолчанию: {_value(question_policy.get('default_mode'))}",
            "",
            "## Открытые вопросы",
            "",
            *_bullet(architecture.get("open_questions", [])),
            "",
            "## Prompt для уточнения",
            "",
            _value(question_policy.get("clarification_prompt")),
            "",
        ]
    )


def render_product_technical_spec_document(spec: dict[str, Any]) -> str:
    primary = dict(spec.get("primary_contract", {}))
    handoff = dict(spec.get("implementation_handoff", {}))
    return "\n".join(
        [
            "# Техническое задание нового проекта",
            "",
            f"Prompt: {_value(dict(spec.get('source_artifact', {})).get('prompt'))}",
            "",
            "## Что нужно сделать",
            "",
            *_bullet(spec.get("scope", [])),
            "",
            "## Решение для реализации",
            "",
            _spec_decision_text(spec),
            "",
            "## Выбранный архитектурный вариант",
            "",
            *_table(["Вариант", "Решение", "Tradeoffs"], [[dict(spec.get("chosen_architecture_option") or {}).get("id"), dict(spec.get("chosen_architecture_option") or {}).get("decision"), dict(spec.get("chosen_architecture_option") or {}).get("tradeoffs")]]),
            "",
            "## Исследовательские подсказки",
            "",
            *_table(["Тема", "Для чего", "Политика проверки"], [[r.get("topic"), r.get("use_for"), r.get("evidence_policy")] for r in spec.get("research_hints", [])]),
            "",
            "## Главный контракт",
            "",
            f"- Имя: {_value(primary.get('name'))}",
            f"- Вход: {_value(primary.get('input'))}",
            f"- Выход: {_value(primary.get('output'))}",
            f"- Side effects: {_value(primary.get('side_effect_policy'))}",
            "",
            "## Компонентные контракты",
            "",
            *_table(["Компонент", "Назначение", "Вход", "Выход"], [[r.get("component"), r.get("purpose"), r.get("input_contract"), r.get("output_contract")] for r in spec.get("component_contracts", [])]),
            "",
            "## Требования",
            "",
            *_table(["ID", "Priority", "Requirement", "Source"], [[r.get("id"), r.get("priority"), r.get("statement"), r.get("source")] for r in spec.get("requirements", [])]),
            "",
            "## Модель ошибок",
            "",
            *_table(["Ошибка", "Обработка", "Источник"], [[r.get("error"), r.get("handling"), r.get("source")] for r in spec.get("error_model", [])]),
            "",
            "## Данные и жизненный цикл",
            "",
            *_table(["Стадия", "Форма"], [[r.get("stage"), r.get("shape")] for r in spec.get("data_lifecycle", [])]),
            "",
            "## Критерии приемки",
            "",
            *_table(["ID", "Критерий", "Проверка"], [[r.get("id"), r.get("criterion"), r.get("verification")] for r in spec.get("acceptance_criteria", [])]),
            "",
            "## Стратегия проверки",
            "",
            *_bullet(_verification_lines(spec)),
            "",
            "## Передача в реализацию",
            "",
            f"- Роль: {_value(handoff.get('recommended_role'))}",
            f"- Режим: {_value(handoff.get('mode'))}",
            f"- Компоненты: {_value(handoff.get('components'))}",
            f"- С чего не начинать: {_value(handoff.get('must_not_start_with'))}",
            "",
            "## Открытые вопросы для ревью",
            "",
            *_bullet(spec.get("open_questions", [])),
            "",
            "## Не-цели",
            "",
            *_bullet(spec.get("non_goals", [])),
            "",
        ]
    )


def _architecture_decision_text(architecture: dict[str, Any]) -> str:
    components = [str(row.get("id")) for row in architecture.get("components", []) if isinstance(row, dict)]
    boundaries = [str(row.get("target")) for row in architecture.get("external_boundaries", []) if isinstance(row, dict)]
    chosen = dict(architecture.get("chosen_architecture_option") or {})
    chosen_text = f"Выбранный вариант: `{_value(chosen.get('id'))}`; причина: {_sentence(chosen.get('decision'))} "
    return (
        chosen_text
        + f"Систему стоит собирать как `{_value(architecture.get('architecture_style'))}`. "
        f"Core должен оставаться отделенным от внешних эффектов: ключевые компоненты `{_value(components[:5])}` "
        f"работают через явные контракты, а опасные границы `{_value(boundaries)}` выносятся в adapters. "
        "Такой разрез дает тестируемую первую версию и оставляет место для замены backend без переписывания core logic."
    )


def _first_slice(architecture: dict[str, Any]) -> list[str]:
    components = [str(row.get("id")) for row in architecture.get("components", []) if isinstance(row, dict)]
    contract = dict(dict(architecture.get("spec_writer_brief") or {}).get("primary_contract") or {})
    result = [
        f"Стабилизировать главный контракт `{_value(contract.get('name'))}`.",
        f"Реализовывать сначала минимальный путь через компоненты: {_value(components[:4])}.",
        "Проверить happy path на fixture/fake adapters до подключения реальных внешних зависимостей.",
    ]
    if architecture.get("external_boundaries"):
        result.append("Все filesystem/network/subprocess/model side effects оставить за adapter boundary.")
    return result


def _assumptions(architecture: dict[str, Any]) -> list[str]:
    policy = dict(architecture.get("open_question_policy") or {})
    if policy.get("decision") == "ask_user_before_spec":
        return ["ТЗ не строится до ответа пользователя на clarification prompt."]
    return [
        "До ответа пользователя открытые вопросы считаются review items, а не блокерами планирования.",
        "Выбирается локальный/fixture-first MVP без production deployment.",
        "Неясные backend решения оформляются как adapters или explicit dependency policy.",
    ]


def _architecture_verification_plan(architecture: dict[str, Any]) -> list[str]:
    focus = list(dict(architecture.get("spec_writer_brief") or {}).get("acceptance_focus") or [])
    if focus:
        return [str(item) for item in focus[:6]]
    return ["Contract tests", "Negative tests", "README/run instructions"]


def _spec_decision_text(spec: dict[str, Any]) -> str:
    primary = dict(spec.get("primary_contract", {}))
    contracts = [str(row.get("component")) for row in spec.get("component_contracts", []) if isinstance(row, dict)]
    chosen = dict(spec.get("chosen_architecture_option") or {})
    return (
        f"ТЗ наследует архитектурный вариант `{_value(chosen.get('id'))}`: {_sentence(chosen.get('decision'))} "
        f"Реализация должна идти от контракта `{_value(primary.get('name'))}` к компонентам "
        f"`{_value(contracts[:6])}`. Сначала фиксируются schemas, ошибки и tests, затем подключаются adapters. "
        "Любая внешняя зависимость должна быть заменяема fake/fixture backend в default verification."
    )


def _verification_lines(spec: dict[str, Any]) -> list[str]:
    strategy = dict(spec.get("verification_strategy") or {})
    lines = []
    for key in ("contract_tests", "negative_tests", "integration_tests", "manual_review"):
        values = strategy.get(key)
        if values:
            lines.append(f"{key}: {_value(values)}")
    return lines


def _table(headers: list[str], rows: list[list[Any]]) -> list[str]:
    if not rows:
        return ["- Нет данных."]
    result = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    for row in rows[:30]:
        result.append("| " + " | ".join(_cell(item) for item in row) + " |")
    return result


def _bullet(values: object) -> list[str]:
    if not isinstance(values, list):
        values = list(values) if values else []
    return [f"- {_value(item)}" for item in values] or ["- Не записано."]


def _cell(value: object) -> str:
    return _value(value).replace("|", "\\|").replace("\n", " ")


def _value(value: object) -> str:
    if value in (None, "", []):
        return "n/a"
    if isinstance(value, list):
        return ", ".join(_value(item) for item in value[:8])
    if isinstance(value, dict):
        return ", ".join(f"{key}={_value(item)}" for key, item in list(value.items())[:8])
    return str(value)


def _sentence(value: object) -> str:
    text = _value(value).rstrip(". ")
    return f"{text}."


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
