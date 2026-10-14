"""Build selected-target quality without discarding ranking evidence."""

from __future__ import annotations

import re
from typing import Any

from .target_quality import semantic_target_quality_report


def selected_candidate_quality(spec: dict[str, Any]) -> dict[str, Any]:
    contract = dict(spec.get("extraction_contract", {}) or {})
    quality = dict(contract.get("semantic_quality", {}) or {})
    target = str(contract.get("candidate") or "")
    if not target:
        return quality
    rows = [dict(row) for row in contract.get("ranked_candidates") or [] if isinstance(row, dict)]
    ranked = [str(row.get("source")) for row in rows]
    evidence = [
        str(row.get("source")) for row in spec.get("source_evidence") or []
        if isinstance(row, dict)
    ]
    report = semantic_target_quality_report(
        target,
        ranked_candidates=ranked,
        source_evidence=evidence,
        selection_reason=str(contract.get("selection_reason") or ""),
        structural_evidence=dict(contract.get("structural_evidence") or {}),
        input_contract=dict(contract.get("input_contract") or {}),
        output_contract=dict(contract.get("output_contract") or {}),
        side_effect_contract=dict(contract.get("side_effects") or {}),
    )
    selected = next((row for row in rows if _canonical(row.get("source")) == _canonical(target)), {})
    report["selection_evidence"] = {
        "ranked_score": selected.get("score"),
        "kind": selected.get("kind"),
        "ranking_reasons": list(selected.get("reasons") or []),
        "dependency_readiness": dict(
            selected.get("dependency_readiness") or contract.get("dependency_readiness") or {}
        ),
    }
    return report


def _canonical(value: object) -> str:
    text = str(value or "").strip().replace("\\", "/")
    return re.sub(r"\s*\(\d+\s+loc\)\s*$", "", text, flags=re.IGNORECASE)
