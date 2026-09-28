"""Semantic context checks for independent hypothesis probes."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .self_improvement_signatures import (
    assess_signature_match,
    normalize_failure_class,
    portable_failure_signature,
    semantic_context,
)


def probe_summary(
    project: Path, probe: dict[str, Any] | None, plan: dict[str, Any]
) -> dict[str, Any]:
    diagnosis = dict((probe or {}).get("diagnosis") or {})
    baseline = dict((probe or {}).get("baseline") or {})
    normalization = dict(plan.get("signature_normalization") or {})
    actual = normalize_failure_class(str(diagnosis.get("failure_class") or ""), normalization)
    signature = portable_failure_signature(
        {"baseline": baseline, "diagnosis": diagnosis}, normalization
    ) if probe else None
    actual = actual or str(signature or "").split("|", 1)[0]
    assessment = assess_signature_match(
        str(signature or ""), str(plan["portable_signature"]), normalization,
    ) if probe else {"matched": True, "match_kind": "not_measured"}
    actual_context = semantic_context({"baseline": baseline}) if probe else []
    expected_context = {str(value) for value in plan.get("semantic_context") or []}
    context_match = not expected_context or bool(expected_context & set(actual_context))
    assessment.update({
        "semantic_context_match": context_match,
        "actual_semantic_context": actual_context,
        "expected_semantic_context": sorted(expected_context),
    })
    return {
        "project": project.name, "project_dir": project.as_posix(),
        "project_min_score": baseline.get("project_min_score"),
        "retrieval_alignment": dict((probe or {}).get("retrieval_alignment") or {}),
        "failure_class": actual or None, "portable_signature": signature,
        "matches_hypothesis": probe is None or bool(assessment["matched"] and context_match),
        "signature_assessment": assessment,
    }
