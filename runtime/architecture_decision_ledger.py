from __future__ import annotations

from typing import Any


def fact_judgment_ledger(
    *,
    summary: dict[str, Any],
    boundaries: list[dict[str, Any]],
    capabilities: list[dict[str, Any]],
    risks: list[dict[str, Any]],
    first_slice: dict[str, Any],
) -> dict[str, Any]:
    facts: list[dict[str, Any]] = [
        {
            "claim": f"Project root is `{summary.get('root')}` with {summary.get('file_count')} files.",
            "evidence_source": "ProjectMapReport.summary",
        }
    ]
    for boundary in boundaries[:3]:
        facts.append(
            {
                "claim": f"Subsystem boundary `{boundary.get('id')}` owns {boundary.get('owned_files')}.",
                "evidence_source": "ProjectMapReport.execution/readiness",
            }
        )
    for capability in capabilities[:4]:
        facts.append(
            {
                "claim": f"Capability candidate `{capability.get('source')}` is present in analysis evidence.",
                "evidence_source": capability.get("source") or "ProjectMapReport.capabilities",
            }
        )
    judgments = [
        {
            "judgment": "Use a bounded first slice before broader subsystem redesign.",
            "based_on": [capability.get("source") for capability in capabilities[:3] if capability.get("source")],
            "confidence": 0.82 if capabilities else 0.55,
            "validation_gate": "SpecWriter must bind the selected target to input/output contracts and negative acceptance.",
        },
        {
            "judgment": f"First slice `{first_slice.get('name')}` is the preferred handoff candidate.",
            "based_on": list(first_slice.get("targets", []) or [])[:4],
            "confidence": 0.86 if first_slice.get("targets") else 0.45,
            "validation_gate": "Implementer handoff is blocked unless the first slice has source-backed targets.",
        },
    ]
    for risk in risks[:3]:
        judgments.append(
            {
                "judgment": f"Risk `{risk.get('category')}` must be carried into TechnicalSpec acceptance.",
                "based_on": [risk.get("evidence_source")],
                "confidence": 0.78,
                "validation_gate": risk.get("acceptance_gate"),
            }
        )
    return {
        "artifact_type": "FactJudgmentLedger",
        "facts": facts,
        "judgments": judgments,
        "principle": "facts are copied from evidence; judgments are decisions with confidence and validation gates",
    }
