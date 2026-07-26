"""Deterministic quality checks for greenfield architecture/spec artifacts."""

from __future__ import annotations

from typing import Any

from .greenfield_documents import render_product_architecture_document, render_product_technical_spec_document


GENERIC_MARKERS = (
    "bounded software package",
    "bounded greenfield package",
    "main entrypoint",
    "request -> response",
    "typed result returned",
    "n/a",
)


def evaluate_greenfield_artifact_quality(*, architecture: dict[str, Any], technical_spec: dict[str, Any] | None) -> dict[str, Any]:
    checks = []
    checks.extend(_architecture_checks(architecture))
    checks.extend(_architecture_document_checks(render_product_architecture_document(architecture)))
    if technical_spec is None:
        checks.append(_check("technical_spec_present", architecture.get("status") == "needs_clarification", "ProductTechnicalSpec or explicit clarification stop", None))
    else:
        checks.extend(_spec_checks(technical_spec))
        checks.extend(_spec_document_checks(render_product_technical_spec_document(technical_spec)))
        checks.append(
            _check(
                "handoff_preserves_primary_contract",
                dict(technical_spec.get("primary_contract") or {}).get("name")
                == dict(dict(architecture.get("spec_writer_brief") or {}).get("primary_contract") or {}).get("name"),
                dict(dict(architecture.get("spec_writer_brief") or {}).get("primary_contract") or {}).get("name"),
                dict(technical_spec.get("primary_contract") or {}).get("name"),
            )
        )
    passed = sum(1 for row in checks if row["passed"])
    score = round(passed / len(checks), 3) if checks else 0.0
    return {
        "artifact_type": "GreenfieldArtifactQualityReport",
        "status": "ok" if score >= 0.9 and passed == len(checks) else "needs_review",
        "score": score,
        "summary": {"checks": len(checks), "passed": passed, "failed": len(checks) - passed},
        "checks": checks,
    }


def _architecture_checks(architecture: dict[str, Any]) -> list[dict[str, Any]]:
    components = [row for row in architecture.get("components", []) if isinstance(row, dict)]
    interfaces = [row for row in architecture.get("interfaces", []) if isinstance(row, dict)]
    data_model = [row for row in architecture.get("data_model", []) if isinstance(row, dict)]
    lifecycle = [row for row in architecture.get("data_lifecycle", []) if isinstance(row, dict)]
    research_hints = [row for row in architecture.get("research_hints", []) if isinstance(row, dict)]
    options = [row for row in architecture.get("architecture_options", []) if isinstance(row, dict)]
    risks = [row for row in architecture.get("risks", []) if isinstance(row, dict)]
    return [
        _check("pattern_specific", architecture.get("pattern_id") not in {None, "", "generic_product"}, "non-generic pattern", architecture.get("pattern_id")),
        _check("architecture_summary_specific", not _has_generic_text(architecture.get("product_summary")), "specific summary", architecture.get("product_summary")),
        _check("components_have_contracts", len([row for row in components if row.get("id") and row.get("inputs") and row.get("outputs")]) >= 3, ">=3 contracted components", len(components)),
        _check("interfaces_present", len(interfaces) >= 1 and all(row.get("input") and row.get("output") for row in interfaces), "interfaces with input/output", interfaces),
        _check("data_model_present", len(data_model) >= 2, ">=2 data model records", len(data_model)),
        _check("data_lifecycle_present", len(lifecycle) >= 4, ">=4 lifecycle stages", len(lifecycle)),
        _check("research_hints_present", len(research_hints) >= 2 and all(row.get("topic") and row.get("evidence_policy") and row.get("authority") for row in research_hints), ">=2 evidence-scoped research hints", research_hints),
        _check("architecture_options_present", len(options) >= 2 and any(row.get("status") == "chosen" for row in options) and any(row.get("status") == "rejected" for row in options), "chosen and rejected options", options),
        _check("risks_have_mitigation", len(risks) >= 2 and all(row.get("risk") and row.get("mitigation") for row in risks), ">=2 mitigated risks", risks),
        _check("open_questions_present", len(architecture.get("open_questions", [])) >= 2, ">=2 open questions", architecture.get("open_questions", [])),
        _check("forbidden_actions_clean", not architecture.get("forbidden_actions_observed"), [], architecture.get("forbidden_actions_observed")),
    ]


def _spec_checks(spec: dict[str, Any]) -> list[dict[str, Any]]:
    requirements = [row for row in spec.get("requirements", []) if isinstance(row, dict)]
    component_contracts = [row for row in spec.get("component_contracts", []) if isinstance(row, dict)]
    acceptance = [row for row in spec.get("acceptance_criteria", []) if isinstance(row, dict)]
    errors = [row for row in spec.get("error_model", []) if isinstance(row, dict)]
    verification = dict(spec.get("verification_strategy") or {})
    return [
        _check("requirements_present", len(requirements) >= 4, ">=4 requirements", len(requirements)),
        _check("requirement_ids_unique", len({row.get("id") for row in requirements}) == len(requirements), "unique ids", [row.get("id") for row in requirements]),
        _check("component_contracts_present", len(component_contracts) >= 3, ">=3 component contracts", len(component_contracts)),
        _check("primary_contract_specific", not _has_generic_text(dict(spec.get("primary_contract") or {}).get("name")), "specific primary contract", dict(spec.get("primary_contract") or {}).get("name")),
        _check("error_model_present", len(errors) >= 2, ">=2 error rows", len(errors)),
        _check("acceptance_present", len(acceptance) >= 3, ">=3 acceptance criteria", len(acceptance)),
        _check("verification_strategy_present", bool(verification.get("contract_tests")) and bool(verification.get("negative_tests")), "contract and negative tests", verification),
        _check("chosen_architecture_option_present", bool(dict(spec.get("chosen_architecture_option") or {}).get("id")), "chosen option carried into spec", spec.get("chosen_architecture_option")),
        _check("implementation_handoff_bounded", dict(spec.get("implementation_handoff") or {}).get("mode") == "greenfield_project", "greenfield_project", dict(spec.get("implementation_handoff") or {}).get("mode")),
        _check("forbidden_actions_clean", not spec.get("forbidden_actions_observed"), [], spec.get("forbidden_actions_observed")),
    ]


def _architecture_document_checks(text: str) -> list[dict[str, Any]]:
    required_sections = [
        "## Архитектурное решение",
        "## Research Hints",
        "## Архитектурные варианты",
        "## Первый полезный срез",
        "## Допущения до уточнения",
        "## План проверки",
        "## Открытые вопросы",
    ]
    return [
        _check("architecture_human_doc_sections", all(section in text for section in required_sections), required_sections, _present_sections(text, required_sections)),
        _check("architecture_human_doc_has_decision_language", "adapter" in text.lower() and "контракт" in text.lower(), "decision text with adapters/contracts", _excerpt(text, "## Архитектурное решение")),
        _check("architecture_human_doc_no_english_intake_questions", not _has_untranslated_intake_question(text), "no untranslated intake questions", _untranslated_questions(text)),
    ]


def _spec_document_checks(text: str) -> list[dict[str, Any]]:
    required_sections = [
        "## Решение для реализации",
        "## Выбранный архитектурный вариант",
        "## Исследовательские подсказки",
        "## Главный контракт",
        "## Данные и жизненный цикл",
        "## Стратегия проверки",
        "## Открытые вопросы для ревью",
    ]
    return [
        _check("spec_human_doc_sections", all(section in text for section in required_sections), required_sections, _present_sections(text, required_sections)),
        _check("spec_human_doc_has_handoff_language", "schemas" in text.lower() and "tests" in text.lower(), "handoff text with schemas/tests", _excerpt(text, "## Решение для реализации")),
        _check("spec_human_doc_no_english_intake_questions", not _has_untranslated_intake_question(text), "no untranslated intake questions", _untranslated_questions(text)),
    ]


def _has_generic_text(value: Any) -> bool:
    text = str(value or "").lower()
    return not text.strip() or any(marker in text for marker in GENERIC_MARKERS)


def _present_sections(text: str, sections: list[str]) -> list[str]:
    return [section for section in sections if section in text]


def _excerpt(text: str, section: str) -> str:
    start = text.find(section)
    if start < 0:
        return ""
    return text[start : start + 360]


def _has_untranslated_intake_question(text: str) -> bool:
    return bool(_untranslated_questions(text))


def _untranslated_questions(text: str) -> list[str]:
    markers = [
        "What bounded system type",
        "What are the concrete inputs",
        "What files, API responses",
        "What constraints should apply",
        "What tests or observable criteria",
        "Are external dependencies allowed",
        "Which narrow first version",
    ]
    return [marker for marker in markers if marker in text]


def _check(name: str, passed: bool, expected: Any, actual: Any) -> dict[str, Any]:
    return {"name": name, "passed": bool(passed), "expected": expected, "actual": actual}
