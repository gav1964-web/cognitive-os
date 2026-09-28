from __future__ import annotations

import ast
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

def write_architecture_analysis_document(
    *,
    root: Path,
    project_report: dict[str, Any],
    architecture_decision: dict[str, Any],
    technical_spec: dict[str, Any] | None = None,
    output_group: str = "foundations",
) -> Path:
    out_dir = root / "artifacts" / "roles" / output_group
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = out_dir / f"architecture_analysis_{stamp}.md"
    path.write_text(
        render_architecture_analysis_document(
            project_report=project_report,
            architecture_decision=architecture_decision,
            technical_spec=technical_spec or {},
        ),
        encoding="utf-8",
    )
    return path

def render_architecture_analysis_document(
    *,
    project_report: dict[str, Any],
    architecture_decision: dict[str, Any],
    technical_spec: dict[str, Any],
) -> str:
    content = dict(project_report.get("content", project_report))
    summary = dict(content.get("summary", {}))
    answers = dict(content.get("answers", {}))
    source_health = dict(content.get("source_health") or answers.get("0_source_health") or {})
    security_health = dict(content.get("security_health") or answers.get("0_security_health") or {})
    chosen = dict(architecture_decision.get("chosen_option", {}))
    contract = dict(technical_spec.get("extraction_contract", {}))
    scope = dict(_first_answer(answers, "1_project_purpose_and_boundaries", "1_scope") or {})
    profile = dict(dict(architecture_decision.get("architecture_synthesis", {})).get("project_profile", {}))
    execution = dict(_first_answer(answers, "2_entrypoints_and_execution_flow", "2_execution") or {})
    readiness = dict(answers.get("6_runtime_extraction_readiness", {}))
    lines = [
        "# Анализ архитектуры",
        "",
        "Документ для человека. Имена файлов, функций и артефактов оставлены без перевода, чтобы не потерять связь с кодом.",
        "Машинная цепочка артефактов: ProjectMapReport -> ArchitectureDecisionRecord -> TechnicalSpec.",
        "",
        f"Проект: {_value(project_report.get('project') or architecture_decision.get('project') or summary.get('root'))}",
        f"Цель анализа: {_ru_text(architecture_decision.get('goal'))}",
        "",
        "## Краткое резюме",
        "",
        _architecture_summary(project_report, architecture_decision, technical_spec),
        "",
        f"Выбранный подход: {_ru_text(chosen.get('title') or chosen.get('id'))}",
        f"Почему так: {_ru_text(chosen.get('reason'))}",
        "",
        "## Отклоненные варианты",
        "",
        *_table(
            ["Вариант", "Почему отложен", "Score delta", "Когда вернуться"],
            [
                [
                    _ru_text(row.get("title") or row.get("id")),
                    _ru_text(row.get("reason_rejected")),
                    row.get("score_delta"),
                    _ru_text(row.get("deferred_until")),
                ]
                for row in architecture_decision.get("rejected_options", [])
                if isinstance(row, dict)
            ],
        ),
        "",
        "## Source health",
        "",
        *_source_health_lines(source_health),
        "",
        "## Security health",
        "",
        *_security_health_lines(security_health),
        "",
        "## Назначение и границы проекта",
        "",
        *_scope_lines(scope, profile),
        "",
        "## Точки входа и поток исполнения",
        "",
        *_execution_lines(execution),
        "",
        "## Ключевые управляющие узлы",
        "",
        *_node_table("central_flow_nodes", execution.get("central_flow_nodes")),
        "",
        "## Проблемные зоны",
        "",
        *_risk_zone_lines(readiness),
        "",
        "## Кандидаты в capabilities",
        "",
        *_table(
            ["Источник", "Почему интересен", "Статус", "Следующий шаг"],
            [
                [row.get("source"), _ru_text(row.get("reason")), _ru_text(row.get("status")), _ru_text(row.get("next_step"))]
                for row in architecture_decision.get("capability_model", [])
            ],
        ),
        "",
        "## Рекомендуемый первый срез",
        "",
        f"Кандидат: `{_value(contract.get('candidate'))}`",
        f"Причина выбора: {_ru_text(contract.get('selection_reason'))}",
        "",
        "## Риски",
        "",
        *_table(
            ["Критичность", "Источник", "Описание", "Что сделать"],
            [
                [_ru_text(row.get("severity")), row.get("source"), _risk_description(row), _risk_mitigation(row)]
                for row in architecture_decision.get("risks", [])
            ],
        ),
        "",
        "## Рекомендации по улучшению",
        "",
        *_improvement_recommendations(answers),
        "",
        "## Эскиз целевой архитектуры",
        "",
        *_target_architecture_sketch(answers),
        "",
        "## Открытые вопросы",
        "",
        *_bullet(row.get("question") for row in architecture_decision.get("open_questions", [])),
        "",
        "## Evidence и трассируемость",
        "",
        *_table(
            ["Источник", "Требование", "Цель", "Приемка"],
            [
                [row.get("source"), _ru_text(row.get("requirement")), row.get("target"), _ru_text(row.get("acceptance"))]
                for row in architecture_decision.get("traceability", [])
            ],
        ),
        "",
        "## Не-цели",
        "",
        *_bullet(architecture_decision.get("non_goals", [])),
        "",
        "## Следующий шаг",
        "",
        _next_step(architecture_decision, technical_spec),
        "",
    ]
    return "\n".join(lines)

def _architecture_summary(
    project_report: dict[str, Any],
    architecture_decision: dict[str, Any],
    technical_spec: dict[str, Any],
) -> str:
    contract = dict(technical_spec.get("extraction_contract", {}))
    candidate = _value(contract.get("candidate"))
    capabilities = len(architecture_decision.get("capability_model", []) or [])
    risks = len(architecture_decision.get("risks", []) or [])
    project = _value(project_report.get("project") or architecture_decision.get("project"))
    if candidate != "n/a":
        return (
            f"Проект `{project}` можно разбирать как кандидат на постепенное выделение capabilities. "
            f"Найдено кандидатов: {capabilities}, рисков: {risks}. "
            f"Первым безопасным срезом выбран `{candidate}`."
        )
    return f"Проект `{project}` проанализирован; найдено кандидатов: {capabilities}, рисков: {risks}."

def _scope_lines(scope: dict[str, Any], profile: dict[str, Any] | None = None) -> list[str]:
    profile = profile or {}
    purpose = profile.get("purpose_summary") or scope.get("main_task")
    scenarios = profile.get("scenario_summary") or scope.get("supported_scenarios")
    inputs = profile.get("input_summary") or scope.get("inputs")
    outputs = profile.get("output_summary") or scope.get("outputs")
    lines = []
    if profile.get("knowledge_rule"):
        lines.append(f"- Архитектурный архетип: {_ru_text(profile.get('label'))} (`{_value(profile.get('knowledge_rule'))}`)")
    return [
        *lines,
        f"- Главная задача: {_ru_text(purpose)}",
        f"- Основные сценарии: {_ru_join(scenarios)}",
        f"- Входы: {_ru_join(inputs)}",
        f"- Выходы: {_ru_join(outputs)}",
        f"- Core logic: {_compact_dict_list(scope.get('code_areas'), 'core_logic')}",
        f"- Интерфейсы и адаптеры: {_compact_dict_list(scope.get('code_areas'), 'interfaces_adapters')}",
        f"- Тестовая поверхность: {_test_surface(scope.get('test_surface'))}",
    ]

def _source_health_lines(source_health: dict[str, Any]) -> list[str]:
    if not source_health:
        return ["- Нет source-health evidence."]
    lines = [
        f"- Статус: `{_value(source_health.get('status'))}`",
        f"- Форма проекта: `{_value(source_health.get('project_shape'))}`",
        f"- SyntaxError: `{_value(source_health.get('syntax_error_count'))}`",
        f"- Недоступные пути: `{_value(source_health.get('inaccessible_count'))}`",
        f"- Generated/duplicated signals: `{_value(source_health.get('generated_run_signal_count'))}`",
        f"- Рекомендация: {_ru_text(source_health.get('recommendation'))}",
    ]
    samples = source_health.get("syntax_error_samples") or []
    if samples:
        lines.append("- Примеры SyntaxError: " + _ru_join([dict(row).get("path") for row in samples[:5] if isinstance(row, dict)]))
    return lines

def _security_health_lines(security_health: dict[str, Any]) -> list[str]:
    if not security_health:
        return ["- Нет security-health evidence."]
    return [
        f"- Статус: `{_value(security_health.get('status'))}`",
        f"- Secret marker hits: `{_value(security_health.get('secret_hit_count'))}`",
        f"- Примеры: {_ru_join(security_health.get('secret_hit_samples'))}",
        f"- Рекомендация: {_ru_text(security_health.get('recommendation'))}",
    ]

def _execution_lines(execution: dict[str, Any]) -> list[str]:
    return [
        f"- Entry points: {_ru_join(execution.get('entrypoints'))}",
        f"- Основной путь: {_ru_join(execution.get('primary_execution_path'), sep=' -> ')}",
        f"- Pipeline-кандидат: {_ru_text(execution.get('pipeline_candidate'))}",
        f"- Команды запуска: {_ru_join(execution.get('runtime_commands'))}",
    ]

def _node_table(name: str, rows: object) -> list[str]:
    if not isinstance(rows, list) or not rows:
        return ["- Нет структурированных данных."]
    return _table(
        ["Узел", "LOC", "Вызовы", "Side effects"],
        [
            [
                _source_ref(row),
                row.get("loc"),
                row.get("call_count"),
                _ru_join(row.get("side_effects")),
            ]
            for row in rows[:8]
            if isinstance(row, dict)
        ],
    )

def _risk_zone_lines(readiness: dict[str, Any]) -> list[str]:
    return [
        f"- Скрытая оркестрация: {_refs_line(readiness.get('hidden_orchestrators'))}",
        f"- Границы process/network/filesystem: {_refs_line(readiness.get('process_boundary_candidates'))}",
        f"- Риски idempotency/retry: {_refs_line(readiness.get('idempotency_risks'), key='target')}",
        f"- Кандидаты на quarantine policy: {_refs_line(readiness.get('quarantine_candidates'), key='target')}",
        f"- Минимальный план извлечения: {_refs_line(dict(readiness.get('minimal_extraction_plan', {})).get('capabilities_to_extract'), key='capability')}",
    ]

def _first_answer(answers: dict[str, Any], *keys: str) -> object:
    for key in keys:
        value = answers.get(key)
        if value not in (None, "", [], {}):
            return value
    return None

def _answer_lines(value: object) -> list[str]:
    if isinstance(value, dict):
        rows = []
        for key, item in value.items():
            rows.append(f"- {key}: {_value(item)}")
        return rows or ["- No structured answer available."]
    if isinstance(value, list):
        return _bullet(value)
    return [f"- {_value(value)}"]

def _improvement_recommendations(answers: dict[str, Any]) -> list[str]:
    readiness = dict(answers.get("6_runtime_extraction_readiness", {}))
    recommendations: list[str] = []

    hidden = _target_refs(readiness.get("hidden_orchestrators", []))
    if hidden:
        recommendations.append("Разрезать скрытые оркестраторы и крупные управляющие функции: " + ", ".join(hidden[:4]) + ".")

    process_boundaries = _target_refs(readiness.get("process_boundary_candidates", []))
    if process_boundaries:
        recommendations.append("Изолировать process/network/filesystem-границы до retry/replay: " + ", ".join(process_boundaries[:4]) + ".")

    idempotency = _target_refs(readiness.get("idempotency_risks", []), key="target")
    if idempotency:
        recommendations.append("Описать idempotency и resume policy для операций с side effects: " + ", ".join(idempotency[:4]) + ".")

    quarantine = _target_refs(readiness.get("quarantine_candidates", []), key="target")
    if quarantine:
        recommendations.append("Добавить quarantine policy для нестабильных зависимостей и внешних границ: " + ", ".join(quarantine[:4]) + ".")

    strategy = readiness.get("contract_test_strategy")
    if isinstance(strategy, list) and strategy:
        recommendations.append("Добавить contract tests вокруг: " + ", ".join(_value(item) for item in strategy[:4]) + ".")

    extraction_plan = dict(readiness.get("minimal_extraction_plan", {}))
    capabilities = _target_refs(extraction_plan.get("capabilities_to_extract", []), key="capability")
    if capabilities:
        recommendations.append("Начать с ограниченных extraction candidates: " + ", ".join(capabilities[:4]) + ".")

    return [f"- {item}" for item in recommendations] or ["- No structured recommendations available."]
