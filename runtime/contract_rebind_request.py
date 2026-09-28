"""Build a bounded request to realign upstream implementation contracts."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def build_contract_rebind_request(
    *,
    target: str,
    reason: str,
    alignment: dict[str, Any],
    technical_spec: dict[str, Any],
    implementation_plan: dict[str, Any],
    test_plan: dict[str, Any],
    acceptance_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Describe a contract repair without mutating any upstream artifact."""
    candidates = _candidate_targets(target, alignment, technical_spec)
    return {
        "artifact_type": "ContractRebindRequest",
        "status": "requested",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "current_target": target,
        "reason": reason,
        "evidence": {
            "contract_alignment": alignment,
            "acceptance_summary": dict(acceptance_summary or {}),
            "technical_spec_candidate": dict(technical_spec.get("extraction_contract") or {}).get("candidate"),
            "implementation_plan_candidate": dict(implementation_plan.get("implementation_target") or {}).get("candidate"),
            "test_plan_status": test_plan.get("status"),
        },
        "candidate_targets": candidates,
        "requested_updates": _requested_updates(alignment),
        "authority": "advisory_no_artifact_or_source_mutation",
        "forbidden_actions": ["edit_source", "rewrite_upstream_artifacts", "promote_candidate_without_verification"],
        "next_step": "return_to_spec_writer_then_rebuild_downstream_artifacts",
    }


def _candidate_targets(target: str, alignment: dict[str, Any], technical_spec: dict[str, Any]) -> list[dict[str, Any]]:
    ranked: list[tuple[str, str]] = []
    for candidate in list(alignment.get("candidate_targets") or []):
        ranked.append((str(candidate), "acceptance_drift_evidence"))
    extraction = dict(technical_spec.get("extraction_contract") or {})
    for row in list(extraction.get("ranked_candidates") or [])[:5]:
        if isinstance(row, dict) and row.get("source"):
            ranked.append((str(row["source"]), "technical_spec_ranked_candidate"))
    if target:
        ranked.append((target, "current_target_reconsideration"))
    seen: set[str] = set()
    candidates: list[dict[str, Any]] = []
    for candidate, source in ranked:
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        candidates.append({"target": candidate, "evidence": source})
    return candidates[:6]


def _requested_updates(alignment: dict[str, Any]) -> list[str]:
    if alignment.get("reason") == "authoritative_source_criterion_mismatch":
        return [
            "TechnicalSpec.acceptance_criteria",
            "TestPlan.executable_acceptance.obligations",
            "ProgrammerTaskTree.acceptance_dependencies",
            "ImplementationPlan.contract_binding_only_if_target_changes_after_adjudication",
        ]
    return [
        "TechnicalSpec.extraction_contract",
        "ImplementationPlan.implementation_target_and_contract_binding",
        "TestPlan.executable_acceptance.obligations",
        "ProgrammerTaskTree.target_and_dependencies",
    ]
