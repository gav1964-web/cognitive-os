"""Align Architect ownership with independently admitted target selection."""

from __future__ import annotations

from typing import Any

from .architect_first_slice_reselection import _revised_architecture_decision


def align_policy_selected_architecture(
    artifacts: dict[str, dict[str, Any]], project_report: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    adr_key = _artifact_key(artifacts, "ArchitectureDecisionRecord")
    spec_key = _artifact_key(artifacts, "TechnicalSpec")
    if not adr_key or not spec_key:
        return artifacts
    adr = dict(artifacts[adr_key]); spec = dict(artifacts[spec_key])
    contract = dict(spec.get("extraction_contract") or {})
    target = str(contract.get("candidate") or "")
    policy_ids = [str(value) for value in contract.get("selection_policy_ids") or []]
    current = {str(value) for value in dict(adr.get("first_slice_contract") or {}).get("targets") or []}
    if not target or not policy_ids or target in current:
        return artifacts
    source_context = {
        str(row.get("source")): dict(row)
        for row in spec.get("source_evidence") or []
        if isinstance(row, dict) and row.get("source")
    }
    if target not in source_context:
        return artifacts
    outcome = {
        "artifact_type": "FirstSliceReselectionOutcome",
        "iteration": len(adr.get("first_slice_reselection_history") or []) + 1,
        "status": "selected",
        "trigger": "promoted_candidate_selection_policy",
        "selected_targets": [target],
        "selection_policy_ids": policy_ids,
        "authority": "architect",
        "source": "promoted policy + TechnicalSpec source evidence",
    }
    revised = _revised_architecture_decision(
        adr, project_report=project_report, expanded_context=source_context,
        selected_targets=[target], outcome=outcome,
    )
    return {**artifacts, adr_key: revised}


def _artifact_key(artifacts: dict[str, dict[str, Any]], artifact_type: str) -> str:
    return next((key for key, row in artifacts.items() if row.get("artifact_type") == artifact_type), "")
