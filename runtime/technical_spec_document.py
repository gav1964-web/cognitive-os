"""Human-readable TechnicalSpec document."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def write_technical_spec_document(
    *,
    root: Path,
    technical_spec: dict[str, Any],
    architecture_decision: dict[str, Any] | None = None,
    project_report: dict[str, Any] | None = None,
    output_group: str = "foundations",
) -> Path:
    out_dir = root / "artifacts" / "roles" / output_group
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = out_dir / f"technical_spec_{stamp}.md"
    path.write_text(
        render_technical_spec_document(
            technical_spec=technical_spec,
            architecture_decision=architecture_decision or {},
            project_report=project_report or {},
        ),
        encoding="utf-8",
    )
    return path


def render_technical_spec_document(
    *,
    technical_spec: dict[str, Any],
    architecture_decision: dict[str, Any] | None = None,
    project_report: dict[str, Any] | None = None,
) -> str:
    architecture_decision = architecture_decision or {}
    project_report = project_report or {}
    content = dict(project_report.get("content", project_report))
    summary = dict(content.get("summary", {}))
    contract = dict(technical_spec.get("extraction_contract", {}))
    semantic_quality = dict(contract.get("semantic_quality", {}))
    handoff = dict(technical_spec.get("implementation_handoff", {}))
    source_artifact = dict(technical_spec.get("source_artifact", {}))
    interface_contracts = list(technical_spec.get("interface_contracts", []) or [])
    work_plan = dict(technical_spec.get("work_plan_contract", {}))
    lines = [
        "# Техническое задание",
        "",
        "Документ для человека. Имена файлов, функций и машинных артефактов оставлены без перевода, чтобы сохранить трассируемость.",
        "Машинная цепочка артефактов: ProjectMapReport -> ArchitectureDecisionRecord -> TechnicalSpec.",
        "",
        f"Проект: {_value(project_report.get('project') or architecture_decision.get('project') or summary.get('root'))}",
        f"Цель: {_ru_text(source_artifact.get('goal') or architecture_decision.get('goal'))}",
        f"Архитектурный вариант: {_ru_text(technical_spec.get('chosen_architecture_option'))}",
        "",
        "## Что нужно сделать",
        "",
        *_ru_bullet(technical_spec.get("scope", [])),
        "",
        "## Главный контракт работ",
        "",
        f"- Целевая функция: `{_value(contract.get('candidate'))}`",
        f"- Оценка выбора: {_value(contract.get('candidate_score'))}",
        f"- Почему выбрана: {_ru_text(contract.get('selection_reason'))}",
        f"- Семантическое качество: {_ru_text(semantic_quality.get('status'))} ({_value(semantic_quality.get('score'))})",
        f"- Почему качество такое: {_ru_join(semantic_quality.get('reasons'))}",
        f"- Семейство контракта: `{_value(contract.get('contract_family'))}`",
        "",
        "## Контракт входа и выхода",
        "",
        *_selected_contract_lines(interface_contracts, contract),
        "",
        "## Validation gates и failure modes",
        "",
        "### Validation gates",
        *_ru_bullet(contract.get("validation_gates", [])),
        "",
        "### Failure modes",
        *_ru_bullet(contract.get("failure_modes", [])),
        "",
        "## Первый рабочий срез",
        "",
        f"- Название: `{_value(work_plan.get('name'))}`",
        f"- Цель: {_ru_text(work_plan.get('goal'))}",
        f"- Источник: {_value(work_plan.get('source'))}",
        f"- Targets: {_value(work_plan.get('targets'))}",
        *_work_plan_contract_relation(work_plan, contract),
        "",
        *_work_plan_lines(work_plan),
        "",
        "## Требования",
        "",
        *_table(
            ["ID", "Приоритет", "Требование", "Источник"],
            [
                [row.get("id"), _ru_text(row.get("priority")), _ru_text(row.get("statement")), row.get("source")]
                for row in technical_spec.get("requirements", [])
                if isinstance(row, dict)
            ][:16],
        ),
        "",
        "## Связанные interface contracts",
        "",
        *_interface_contract_lines(interface_contracts),
        "",
        "## Жизненный цикл данных",
        "",
        *_table(
            ["Стадия", "Форма данных", "Ожидание контракта", "Evidence"],
            [
                [_ru_text(row.get("stage")), _ru_text(row.get("shape")), _ru_text(row.get("contract_expectation")), row.get("evidence")]
                for row in technical_spec.get("data_lifecycle", [])
                if isinstance(row, dict)
            ],
        ),
        "",
        "## Модель ошибок",
        "",
        *_table(
            ["Ошибка", "Как обрабатывать", "Источник"],
            [
                [_ru_text(row.get("error")), _ru_text(row.get("handling")), row.get("source")]
                for row in technical_spec.get("error_model", [])
                if isinstance(row, dict)
            ],
        ),
        "",
        "## Критерии приемки",
        "",
        *_table(
            ["ID", "Критерий", "Проверка", "Источник"],
            [
                [row.get("id"), _ru_text(row.get("criterion")), _ru_text(row.get("verification")), row.get("source")]
                for row in technical_spec.get("acceptance_criteria", [])
                if isinstance(row, dict)
            ][:20],
        ),
        "",
        "## Трассируемость",
        "",
        *_table(
            ["Источник", "Требование", "Приемка"],
            [
                [row.get("source"), _ru_text(row.get("requirement")), row.get("acceptance_id")]
                for row in technical_spec.get("traceability_table", [])
                if isinstance(row, dict)
            ][:20],
        ),
        "",
        "## Состояние и replay policy",
        "",
        *_table(
            ["Владелец", "Тип", "Жизненный срок", "Resume policy"],
            [
                [_ru_text(row.get("owner")), _ru_text(row.get("kind")), _ru_text(row.get("lifetime")), _ru_text(row.get("resume_policy"))]
                for row in technical_spec.get("state_and_replay_policy", [])
                if isinstance(row, dict)
            ],
        ),
        "",
        "## Стратегия проверки",
        "",
        *_verification_lines(technical_spec.get("verification_strategy", {})),
        "",
        "## Передача в реализацию",
        "",
        f"- Рекомендуемая роль: {_value(handoff.get('recommended_role'))}",
        f"- Ожидаемый выход: {_value(handoff.get('expected_output'))}",
        f"- Границы patch: {_value(handoff.get('patch_scope'))}",
        "",
        "## Ограничения",
        "",
        *_ru_bullet(technical_spec.get("constraints", [])),
        "",
        "## Не-цели",
        "",
        *_ru_bullet(technical_spec.get("non_goals", [])),
        "",
        "## Открытые вопросы",
        "",
        *_open_question_lines(technical_spec.get("open_questions", [])),
        "",
    ]
    return "\n".join(lines)


def _interface_contract_lines(rows: object) -> list[str]:
    if not isinstance(rows, list) or not rows:
        return ["- Связанные interface contracts не записаны."]
    lines: list[str] = []
    for row in rows[:12]:
        if not isinstance(row, dict):
            continue
        lines.extend(
            [
                f"### {_value(row.get('source'))}",
                "",
                f"- Вход: {_value(row.get('input_contract'))}",
                f"- Выход: {_value(row.get('output_contract'))}",
                f"- Side effects: {_value(dict(row.get('side_effect_policy', {})).get('declared'))}",
                f"- Retry policy: {_ru_text(dict(row.get('side_effect_policy', {})).get('retry_policy'))}",
                "",
            ]
        )
    return lines or ["- Связанные interface contracts не записаны."]


def _selected_contract_lines(rows: list[object], contract: dict[str, Any]) -> list[str]:
    candidate = str(contract.get("candidate") or "")
    selected = next((dict(row) for row in rows if isinstance(row, dict) and str(row.get("source") or "") == candidate), {})
    if not selected:
        return [
            f"- Вход: {_value(contract.get('input_contract'))}",
            f"- Выход: {_value(contract.get('output_contract'))}",
            f"- Side effects: {_value(dict(contract.get('side_effects', {})).get('declared'))}",
        ]
    policy = dict(selected.get("side_effect_policy", {}))
    return [
        f"- Вход: {_value(selected.get('input_contract'))}",
        f"- Выход: {_value(selected.get('output_contract'))}",
        f"- Side effects: {_value(policy.get('declared'))}",
        f"- Retry policy: {_ru_text(policy.get('retry_policy'))}",
    ]


def _verification_lines(value: object) -> list[str]:
    if not isinstance(value, dict) or not value:
        return ["- Стратегия проверки не записана."]
    rows: list[str] = []
    labels = {
        "contract_tests": "Контрактные тесты",
        "negative_tests": "Негативные тесты",
        "replay_checks": "Replay/retry checks",
        "work_plan_checks": "Проверки рабочего среза",
    }
    for key in ("contract_tests", "negative_tests", "replay_checks", "work_plan_checks"):
        rows.append(f"### {labels[key]}")
        items = value.get(key, [])
        rows.extend(_ru_bullet(items))
        rows.append("")
    return rows


def _work_plan_lines(value: object) -> list[str]:
    if not isinstance(value, dict):
        return ["- Work plan contract не записан."]
    obligations = value.get("obligations", [])
    if not isinstance(obligations, list) or not obligations:
        return ["- Обязательства рабочего среза не записаны."]
    return _table(
        ["ID", "Шаг", "Target", "Проверка"],
        [
            [row.get("id"), _ru_text(row.get("step")), row.get("target"), _ru_text(row.get("verification"))]
            for row in obligations
            if isinstance(row, dict)
        ][:12],
    )


def _work_plan_contract_relation(work_plan: dict[str, Any], contract: dict[str, Any]) -> list[str]:
    candidate = str(contract.get("candidate") or "")
    targets = [str(item) for item in list(work_plan.get("targets", []) or []) if item]
    if not candidate or candidate == "n/a" or not targets:
        return []
    if any(_same_source(candidate, target) for target in targets):
        return ["- Связь с главным контрактом: целевая функция входит в первый рабочий срез и должна получить отдельный I/O contract."]
    return [
        "- Связь с главным контрактом: целевая функция выбрана как самый безопасный внутренний capability; "
        "первый рабочий срез показывает более широкий пользовательский workflow, в который этот контракт должен быть встроен или с которым должен быть согласован перед реализацией."
    ]


def _same_source(left: str, right: str) -> bool:
    left_clean = left.split("(", 1)[0].strip()
    right_clean = right.split("(", 1)[0].strip()
    return left_clean == right_clean or left_clean.endswith(right_clean) or right_clean.endswith(left_clean)


def _open_question_lines(rows: object) -> list[str]:
    if not isinstance(rows, list) or not rows:
        return ["- Не зафиксированы."]
    return _ru_bullet(row.get("question") if isinstance(row, dict) else row for row in rows)


def _table(headers: list[str], rows: list[list[object]]) -> list[str]:
    if not rows:
        return ["No rows recorded."]
    result = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    for row in rows[:40]:
        result.append("| " + " | ".join(_cell(value) for value in row) + " |")
    return result


def _bullet(values: object) -> list[str]:
    if not isinstance(values, list):
        values = list(values) if values else []
    rows = [f"- {_value(value)}" for value in values if _value(value) != "n/a"]
    return rows or ["- Не записано."]


def _ru_bullet(values: object) -> list[str]:
    if not isinstance(values, list):
        values = list(values) if values else []
    rows = [f"- {_ru_text(value)}" for value in values if _value(value) != "n/a"]
    return rows or ["- Не записано."]


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
        "minimal_safe_extraction": "минимальное безопасное выделение",
        "Extract the safest focused capability first.": "Сначала выделить самый безопасный ограниченный capability.",
        "Prepare one implementable capability extraction spec.": "Подготовить реализуемое ТЗ на выделение одного capability.",
        "MUST": "обязательно",
        "SHOULD": "желательно",
        "strong": "сильный кандидат",
        "acceptable": "приемлемый кандидат",
        "suspicious": "требует проверки",
        "poor": "слабый кандидат",
        "selected extraction candidate exists": "кандидат выбран",
        "candidate is ranked first by SpecWriter": "SpecWriter поставил его первым в ранжировании",
        "candidate is present in source evidence": "кандидат присутствует в source evidence",
        "candidate name suggests a bounded contract": "имя функции похоже на ограниченный контракт",
        "safe to retry if pure contract holds": "можно повторять, если сохраняется чистый контракт",
        "only after checkpoint/idempotency guard": "только после checkpoint/idempotency guard",
        "input must be validated and recorded before transformation": "вход нужно валидировать и фиксировать до преобразования",
        "intermediate shape must be named before handoff": "промежуточную форму данных нужно явно назвать перед передачей дальше",
        "output must match declared schema or artifact path policy": "выход должен соответствовать объявленной схеме или политике artifact path",
        "Reject malformed input at the selected capability boundary with a typed error result.": "Отклонять некорректный вход на границе выбранного capability и возвращать типизированную ошибку.",
        "Stop the handoff and return to SpecWriter/Architect when observed data violates the declared I/O contract.": "Остановить handoff и вернуть задачу в SpecWriter/Architect, если данные нарушают объявленный I/O contract.",
        "pytest or explicit review checklist": "pytest или явный review checklist",
        "Capability candidate requires TechnicalSpec.": "Кандидату нужен TechnicalSpec.",
        "Risk must be addressed or accepted before promotion.": "Риск нужно устранить или явно принять до promotion.",
        "Implementation does not mutate Capability Registry outside explicit Foundry promote.": "Реализация не меняет Capability Registry вне явного Foundry promote.",
        "no source rewrite in spec phase": "на этапе ТЗ исходный код не переписывать",
        "do not rewrite whole project": "не переписывать весь проект",
    }
    if text in replacements:
        return replacements[text]
    if text.endswith(" must have explicit input/output contract, side-effect policy, and Foundry quality gate."):
        source = text.removesuffix(" must have explicit input/output contract, side-effect policy, and Foundry quality gate.")
        return f"Для `{source}` нужно явно описать вход/выход, side-effect policy и Foundry quality gate."
    if text.endswith(" has a bounded TechnicalSpec with source evidence, input contract, output contract, and negative-test expectation."):
        source = text.removesuffix(" has a bounded TechnicalSpec with source evidence, input contract, output contract, and negative-test expectation.")
        return f"`{source}` имеет ограниченное ТЗ с source evidence, входным/выходным контрактом и ожиданием negative tests."
    if "broad function can anchor a meaningful first slice" in text:
        return (
            "функция достаточно крупная, чтобы стать осмысленным первым срезом; "
            "нет заявленных side effects; контракт входа/выхода выводится из сигнатуры; "
            "есть source-backed snippet; граница выглядит полезной для архитектуры"
        )
    return text
