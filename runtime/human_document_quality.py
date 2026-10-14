"""Quality checks for human-readable role documents."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def evaluate_human_role_documents(
    *,
    architecture_document: str | Path | None,
    technical_spec_document: str | Path | None,
) -> dict[str, Any]:
    architecture_text = _read_text(architecture_document)
    spec_text = _read_text(technical_spec_document)
    checks = {
        "architecture_document_present": bool(architecture_text),
        "architecture_document_has_summary": "## Краткое резюме" in architecture_text,
        "architecture_document_has_recommendations": "## Рекомендации по улучшению" in architecture_text,
        "architecture_document_has_evidence": "## Evidence и трассируемость" in architecture_text,
        "architecture_document_mentions_open_questions": "## Открытые вопросы" in architecture_text,
        "technical_spec_document_present": bool(spec_text),
        "technical_spec_has_main_contract": "## Главный контракт работ" in spec_text,
        "technical_spec_has_io_contract": "## Контракт входа и выхода" in spec_text,
        "technical_spec_has_validation_gates": "## Validation gates и failure modes" in spec_text,
        "technical_spec_has_acceptance": "## Критерии приемки" in spec_text,
        "technical_spec_has_handoff": "## Передача в реализацию" in spec_text,
        "documents_are_ru_human_readable": _has_cyrillic(architecture_text) and _has_cyrillic(spec_text),
        "documents_preserve_machine_terms": all(term in architecture_text + "\n" + spec_text for term in ("ProjectMapReport", "TechnicalSpec")),
        "documents_do_not_look_empty": len(architecture_text.split()) >= 80 and len(spec_text.split()) >= 80,
    }
    warnings = [name for name, ok in checks.items() if not ok]
    return {
        "artifact_type": "HumanRoleDocumentQualityReport",
        "status": "pass" if not warnings else "fail",
        "score": _ratio(sum(1 for ok in checks.values() if ok), len(checks)),
        "checks": checks,
        "warnings": warnings,
    }


def _read_text(path: str | Path | None) -> str:
    if not path:
        return ""
    try:
        return Path(path).read_text(encoding="utf-8")
    except OSError:
        return ""


def _has_cyrillic(text: str) -> bool:
    return any("а" <= char.lower() <= "я" or char.lower() == "ё" for char in text)


def _ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0
