"""Role questionnaire section builders."""

from __future__ import annotations

from typing import Any

from .role_knowledge import ROLE_ORDER
from .role_questionnaire_answers import (
    _architecture_field,
    _minimal_plan,
    _capability_candidates,
    _first_capability,
    _external_surface,
    _confidence,
    _non_goals,
    _manual_decisions,
    _spec_contract_target,
    _contract_field,
    _goal_spec,
    _acceptance_criteria,
    _error_surface,
    _spec_out_of_scope,
    _open_questions,
    _verification_artifacts,
    _adapter_candidates,
    _patch_strategy,
    _implementation_blockers,
    _rollout_plan,
    _test_surface,
    _contract_tests,
    _negative_tests,
    _fixtures,
    _smoke_test,
    _regression_tests,
    _test_gaps,
    _test_priority,
    _blocking_risks,
    _security_risks,
    _observability,
    _source_noise,
    _ambiguous_facts,
    _kb_impact,
    _release_decision,
    _approvals,
    _official_docs_need,
    _package_metadata_need,
    _comparable_repo_need,
    _kb_candidates,
    _facts_vs_judgments,
    _kb_confirmations,
    _freshness,
    _allowed_sources,
    _unresolved_sources,
    _admission_status,
)

QUESTION_COUNT_PER_ROLE = 12


def build_questionnaire_sections(ctx: Any) -> list[dict[str, Any]]:
    return [
        _project_analyzer_section(ctx),
        _architect_section(ctx),
        _spec_writer_section(ctx),
        _implementer_section(ctx),
        _tester_section(ctx),
        _reviewer_section(ctx),
        _researcher_section(ctx),
    ]


def _project_analyzer_section(ctx: _Context) -> dict[str, Any]:
    return _section(
        "project_analyzer",
        [
            _qa("Какую главную пользовательскую задачу решает проект?", ctx.scope.get("main_task"), ["answers.1_scope.main_task"]),
            _qa("Какие основные сценарии использования видны по коду?", ctx.scope.get("supported_scenarios"), ["answers.1_scope.supported_scenarios"]),
            _qa("Что является входом проекта?", ctx.scope.get("inputs"), ["answers.1_scope.inputs"]),
            _qa("Что является выходом проекта?", ctx.scope.get("outputs"), ["answers.1_scope.outputs"]),
            _qa("Какие entrypoints обнаружены?", ctx.execution.get("entrypoints") or ctx.summary.get("entrypoints"), ["answers.2_execution.entrypoints", "summary.entrypoints"]),
            _qa("Как выглядит основной execution path?", ctx.execution.get("primary_execution_path"), ["answers.2_execution.primary_execution_path"]),
            _qa("Какие фреймворки и языки определены?", {"frameworks": ctx.summary.get("frameworks"), "languages": ctx.summary.get("languages")}, ["summary"]),
            _qa("Какие узлы управляют потоком исполнения?", ctx.execution.get("central_flow_nodes"), ["answers.2_execution.central_flow_nodes"]),
            _qa("Где есть скрытая оркестрация?", ctx.readiness.get("hidden_orchestrators"), ["answers.6_runtime_extraction_readiness.hidden_orchestrators"]),
            _qa("Какие функции смешивают несколько обязанностей?", ctx.readiness.get("mixed_responsibility_functions"), ["answers.6_runtime_extraction_readiness.mixed_responsibility_functions"]),
            _qa("Какие внешние зависимости и side effects видны?", _external_surface(ctx), ["extract_python_structure.project_insights", "answers.6_runtime_extraction_readiness"]),
            _qa("Какой проектный архетип предполагается?", _architecture_field(ctx, "matched_rule"), ["architecture_synthesis.matched_rule"], confidence="medium"),
        ],
    )


def _architect_section(ctx: _Context) -> dict[str, Any]:
    return _section(
        "architect",
        [
            _qa("Какую целевую архитектурную форму стоит выбрать?", _architecture_field(ctx, "target_shape"), ["architecture_synthesis.target_shape"], confidence="medium"),
            _qa("Какая первая безопасная граница изменения?", _minimal_plan(ctx), ["answers.6_runtime_extraction_readiness.minimal_extraction_plan"]),
            _qa("Какие subsystem boundaries нужно зафиксировать?", ctx.readiness.get("source_strata"), ["answers.6_runtime_extraction_readiness.source_strata"], confidence="medium"),
            _qa("Какие архитектурные риски блокируют быстрый рефакторинг?", ctx.project_report.get("risks"), ["ProjectMapReport.risks"]),
            _qa("Где нужен process boundary?", ctx.readiness.get("process_boundary_candidates"), ["answers.6_runtime_extraction_readiness.process_boundary_candidates"]),
            _qa("Какие capability candidates можно вынести первыми?", _capability_candidates(ctx), ["answers.3_capabilities", "answers.6_runtime_extraction_readiness.minimal_extraction_plan"]),
            _qa("Что нельзя трогать на первом шаге?", _non_goals(ctx), ["role policy", "source_strata"]),
            _qa("Где возможна on-demand quarantine политика?", ctx.readiness.get("quarantine_candidates"), ["answers.6_runtime_extraction_readiness.quarantine_candidates"]),
            _qa("Какой уровень уверенности у решения?", _confidence(ctx), ["level35_project_signals", "architecture_synthesis"]),
            _qa("Какие знания KB сработали?", _architecture_field(ctx, "knowledge_matches"), ["architecture_synthesis.knowledge_matches"], confidence="medium"),
            _qa("Какие решения должны остаться ручными?", _manual_decisions(ctx), ["analysis_tasks", "architecture_synthesis"]),
            _qa("Какой следующий контракт передать SpecWriter?", _spec_contract_target(ctx), ["minimal_extraction_plan", "architecture_synthesis"]),
        ],
    )


def _spec_writer_section(ctx: _Context) -> dict[str, Any]:
    target = _first_capability(ctx)
    return _section(
        "spec_writer",
        [
            _qa("Как сформулировать GoalSpec для первого slice?", _goal_spec(ctx, target), ["goal", "minimal_extraction_plan"]),
            _qa("Какой input contract нужен?", _contract_field(ctx, "explicit_input_schemas", target), ["answers.4_contracts_data"], confidence="medium"),
            _qa("Какой output contract нужен?", _contract_field(ctx, "explicit_output_schemas", target), ["answers.4_contracts_data"], confidence="medium"),
            _qa("Какие структуры данных проходят между модулями?", ctx.contracts.get("data_structures"), ["answers.4_contracts_data.data_structures"]),
            _qa("Где данные передаются слабо типизированно?", ctx.contracts.get("weak_contract_zones"), ["answers.4_contracts_data.weak_contract_zones"]),
            _qa("Какие acceptance criteria нужны?", _acceptance_criteria(ctx, target), ["analysis_tasks", "minimal_extraction_plan"]),
            _qa("Какие ошибки нужно описать явно?", _error_surface(ctx), ["answers.5_errors_state_repro"]),
            _qa("Какие внешние зависимости должны быть разрешены или запрещены?", _external_surface(ctx), ["project_insights.external_imports"]),
            _qa("Какие промежуточные артефакты стоит сохранять?", ctx.contracts.get("intermediate_artifacts"), ["answers.4_contracts_data.intermediate_artifacts"]),
            _qa("Что остается out of scope?", _spec_out_of_scope(ctx), ["role policy"]),
            _qa("Какие вопросы нужно уточнить до реализации?", _open_questions(ctx), ["analysis_tasks", "knowledge_gap"], confidence="medium"),
            _qa("Какие verification artifacts ожидаются?", _verification_artifacts(ctx, target), ["test_surface", "runtime_commands"]),
        ],
    )


def _implementer_section(ctx: _Context) -> dict[str, Any]:
    target = _first_capability(ctx)
    return _section(
        "implementer",
        [
            _qa("Какие файлы/символы являются первой целью изменения?", target, ["minimal_extraction_plan.capabilities_to_extract"]),
            _qa("Какой минимальный extraction plan?", _minimal_plan(ctx), ["answers.6_runtime_extraction_readiness.minimal_extraction_plan"]),
            _qa("Какие чистые transforms можно вынести без риска?", ctx.capabilities.get("pure_transforms"), ["answers.3_capabilities.pure_transforms"]),
            _qa("Какие широкие функции нужно резать?", ctx.capabilities.get("too_broad_functions"), ["answers.3_capabilities.too_broad_functions"]),
            _qa("Где нужны adapters?", _adapter_candidates(ctx), ["entrypoints", "external_imports"]),
            _qa("Где нужен schema layer?", ctx.contracts.get("explicit_schemas") or ctx.contracts.get("weak_contract_zones"), ["answers.4_contracts_data"]),
            _qa("Какие операции нельзя безопасно повторять?", ctx.readiness.get("idempotency_risks"), ["answers.6_runtime_extraction_readiness.idempotency_risks"]),
            _qa("Что можно checkpoint/resume?", ctx.readiness.get("resume_reuse_plan"), ["answers.6_runtime_extraction_readiness.resume_reuse_plan"]),
            _qa("Что лучше изолировать через process boundary?", ctx.readiness.get("process_boundary_candidates"), ["answers.6_runtime_extraction_readiness.process_boundary_candidates"]),
            _qa("Какой patch strategy безопасен?", _patch_strategy(ctx, target), ["role policy", "source_strata"]),
            _qa("Какие blockers у реализации?", _implementation_blockers(ctx), ["minimal_extraction_plan.blocked_by", "open_questions"], confidence="medium"),
            _qa("Какой rollout plan минимален?", _rollout_plan(ctx, target), ["minimal_extraction_plan", "runtime_commands"]),
        ],
    )


def _tester_section(ctx: _Context) -> dict[str, Any]:
    target = _first_capability(ctx)
    return _section(
        "tester",
        [
            _qa("Какая существующая test surface обнаружена?", _test_surface(ctx), ["extract_python_structure.project_insights.test_surface"]),
            _qa("Какие contract tests можно построить автоматически?", _contract_tests(ctx, target), ["answers.4_contracts_data", "minimal_extraction_plan"]),
            _qa("Где нужны hand-written negative tests?", _negative_tests(ctx), ["answers.5_errors_state_repro", "quarantine_candidates"]),
            _qa("Какие fixtures/fakes нужны для внешних зависимостей?", _fixtures(ctx), ["project_insights.external_imports"]),
            _qa("Какой smoke test минимален?", _smoke_test(ctx), ["extract_runtime_commands", "entrypoints"]),
            _qa("Что тестировать на idempotency?", ctx.readiness.get("idempotency_risks"), ["answers.6_runtime_extraction_readiness.idempotency_risks"]),
            _qa("Что тестировать на replay/resume?", ctx.readiness.get("resume_reuse_plan"), ["answers.6_runtime_extraction_readiness.resume_reuse_plan"]),
            _qa("Какие process-boundary tests нужны?", ctx.readiness.get("process_boundary_candidates"), ["answers.6_runtime_extraction_readiness.process_boundary_candidates"]),
            _qa("Где вероятен parser/API drift?", ctx.readiness.get("quarantine_candidates"), ["answers.6_runtime_extraction_readiness.quarantine_candidates"]),
            _qa("Какие regression tests приоритетны?", _regression_tests(ctx, target), ["central_flow_nodes", "minimal_extraction_plan"]),
            _qa("Какие gaps в тестировании остаются?", _test_gaps(ctx), ["test_surface", "open_questions"], confidence="medium"),
            _qa("Какой порядок тестирования?", _test_priority(ctx, target), ["role policy", "risks"]),
        ],
    )


def _reviewer_section(ctx: _Context) -> dict[str, Any]:
    return _section(
        "reviewer",
        [
            _qa("Есть ли blocking risks?", _blocking_risks(ctx), ["ProjectMapReport.risks", "analysis_tasks"]),
            _qa("Есть ли security/privacy risks?", _security_risks(ctx), ["imports", "weak_contract_zones"], confidence="medium"),
            _qa("Соблюдена ли source edit safety policy?", "Да: questionnaire only; source projects are read-only evidence.", ["report.policy"]),
            _qa("Есть ли dependency drift risk?", ctx.readiness.get("quarantine_candidates"), ["quarantine_candidates"]),
            _qa("Достаточно ли error taxonomy?", _error_surface(ctx), ["answers.5_errors_state_repro"]),
            _qa("Есть ли state/replay risk?", ctx.readiness.get("resume_reuse_plan"), ["resume_reuse_plan"], confidence="medium"),
            _qa("Хватает ли observability/logging?", _observability(ctx), ["project_insights", "runtime_commands"], confidence="medium"),
            _qa("Не загрязнен ли анализ docs/tests/examples?", _source_noise(ctx), ["source_strata"], confidence="medium"),
            _qa("Какие факты выглядят неоднозначными?", _ambiguous_facts(ctx), ["open_questions", "knowledge_gap"], confidence="medium"),
            _qa("Какой KB impact у проекта?", _kb_impact(ctx), ["architecture_synthesis", "knowledge_gap"], confidence="medium"),
            _qa("Какое release decision по первому slice?", _release_decision(ctx), ["risks", "minimal_extraction_plan"]),
            _qa("Какие approvals нужны?", _approvals(ctx), ["role policy", "risk surface"]),
        ],
    )


def _researcher_section(ctx: _Context) -> dict[str, Any]:
    return _section(
        "researcher",
        [
            _qa("Какие knowledge gaps обнаружены?", ctx.knowledge_gap, ["project_research_gap_from_synthesis"], confidence="medium"),
            _qa("Нужны ли official docs?", _official_docs_need(ctx), ["knowledge_gap", "external_imports"], confidence="medium"),
            _qa("Нужны ли PyPI/package metadata?", _package_metadata_need(ctx), ["detect_project_stack", "external_imports"], confidence="medium"),
            _qa("Нужны ли comparable GitHub repos?", _comparable_repo_need(ctx), ["matched_rule", "architecture_synthesis"], confidence="medium"),
            _qa("Какие KB candidates можно предложить?", _kb_candidates(ctx), ["architecture_synthesis", "knowledge_gap"], confidence="medium"),
            _qa("Какая source policy для исследования?", "Prefer official docs and project-owned files; treat internet/GitHub findings as evidence, not truth.", ["EXTERNAL_RESEARCH_LOOP_SPEC"]),
            _qa("Где факты, а где judgments?", _facts_vs_judgments(ctx), ["ProjectMapReport", "ArchitectureSynthesis"]),
            _qa("Какие подтверждения нужны до KB admission?", _kb_confirmations(ctx), ["ROLE_KNOWLEDGE_BASE_SPEC"], confidence="medium"),
            _qa("Есть ли stale/fresh facts?", _freshness(ctx), ["external_research_policy"], confidence="medium"),
            _qa("Какие источники разрешены?", _allowed_sources(ctx), ["EXTERNAL_RESEARCH_LOOP_SPEC"]),
            _qa("Какие unresolved sources остаются?", _unresolved_sources(ctx), ["research_plan"], confidence="medium"),
            _qa("Какой admission status?", _admission_status(ctx), ["knowledge_gap", "review policy"], confidence="medium"),
        ],
    )


def _section(role: str, answers: list[dict[str, Any]]) -> dict[str, Any]:
    if role not in ROLE_ORDER:
        raise ValueError(f"unknown role: {role}")
    return {"role": role, "question_count": len(answers), "answers": answers}


def _qa(
    question: str,
    answer: Any,
    evidence: list[str],
    *,
    confidence: str | None = None,
    gaps: list[str] | None = None,
) -> dict[str, Any]:
    compact = _compact(answer)
    inferred_gaps = list(gaps or [])
    if compact in {"unknown", "[]", "{}"}:
        inferred_gaps.append("not enough evidence in ProjectMapReport")
    return {
        "question": question,
        "answer": compact,
        "evidence": evidence,
        "confidence": confidence or ("low" if inferred_gaps else "high"),
        "gaps": inferred_gaps,
    }


def _compact(value: Any) -> str:
    if value is None or value == "":
        return "unknown"
    if isinstance(value, str):
        return value[:800]
    if isinstance(value, dict):
        items = []
        for key, item in list(value.items())[:8]:
            compact = _compact(item)
            if compact != "unknown":
                items.append(f"{key}: {compact}")
        return "; ".join(items)[:1000] if items else "{}"
    if isinstance(value, list):
        parts = [_compact(item) for item in value[:8]]
        parts = [part for part in parts if part != "unknown"]
        return "; ".join(parts)[:1000] if parts else "[]"
    return str(value)[:800]
