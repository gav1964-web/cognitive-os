"""Validate TestPlan targets against an atomic Programmer change set."""

from __future__ import annotations

import re
from typing import Any


def contract_alignment(
    target: str,
    test_plan: dict[str, Any],
    *,
    allowed_targets: list[str] | None = None,
) -> dict[str, Any]:
    obligations = list(dict(test_plan.get("executable_acceptance") or {}).get("obligations") or [])
    accepted_targets = {target, *(allowed_targets or [])} - {""}
    obligation_targets = {
        str(item.get("target") or "")
        for item in obligations
        if isinstance(item, dict) and item.get("target")
    }
    target_mismatches = sorted(obligation_targets - accepted_targets)
    criterion_refs = [
        (str(item.get("source_criterion") or ""), ref)
        for item in obligations
        if isinstance(item, dict)
        for ref in set(
            re.findall(
                r"[\w./-]+\.py:[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*",
                str(item.get("source_criterion") or ""),
            )
        )
    ]
    refs = sorted({ref for _, ref in criterion_refs})
    mismatches = [ref for ref in refs if target and ref not in accepted_targets]
    direct = sorted(
        ref
        for criterion, ref in criterion_refs
        if ref not in accepted_targets and "selected extraction_contract" in criterion.lower()
    )
    counts = {ref: sum(1 for _, candidate in criterion_refs if candidate == ref) for ref in mismatches}
    repeated = sorted(ref for ref, count in counts.items() if count >= 2)
    candidates = list(dict.fromkeys(target_mismatches + direct + repeated))[:5]
    if target_mismatches or direct or repeated:
        return {
            "status": "target_drift",
            "reason": "obligation_target_mismatch" if target_mismatches else "authoritative_source_criterion_mismatch",
            "target": target,
            "mismatched_targets": target_mismatches[:5],
            "source_refs": mismatches[:5],
            "candidate_targets": candidates,
        }
    return {
        "status": "aligned",
        "target": target,
        "mismatched_targets": [],
        "source_refs": mismatches[:5],
        "candidate_targets": [],
    }
