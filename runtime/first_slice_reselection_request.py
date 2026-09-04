"""Architect handoff when an approved first slice has no executable target."""

from __future__ import annotations

from typing import Any

from .architect_semantic_admission import semantic_threshold_satisfied
from .executable_acceptance_policy import dependency_stub_policy
from .promoted_candidate_selection_policies import selection_policy_mismatches
from .technical_spec_policy import load_technical_spec_policy


def build_first_slice_reselection_request(
    extraction_contract: dict[str, Any], dependency_profile: dict[str, Any]
) -> dict[str, Any]:
    semantic_block = extraction_contract.get("status") == "blocked_no_safe_candidate"
    structural = dict(extraction_contract.get("structural_evidence") or {})
    source_unbound = bool(extraction_contract.get("candidate")) and structural.get("source_body_available") is False
    source_context_blocked = bool(dependency_profile.get("source_context_blockers"))
    viability = dict(extraction_contract.get("first_slice_viability") or {})
    viability_blocked = viability.get("status") == "deferred" or viability.get("reselection_required") is True
    semantic_quality = dict(extraction_contract.get("semantic_quality") or {})
    reselection_policy = dict(load_technical_spec_policy().get("first_slice_reselection") or {})
    semantic_minimum = int(reselection_policy.get("minimum_semantic_score") or 0)
    semantic_score = int(semantic_quality.get("score") or 0)
    semantic_below_threshold = (
        bool(extraction_contract.get("candidate") and semantic_quality)
        and not semantic_threshold_satisfied(
            {
                "semantic_score": semantic_score,
                "semantic_status": semantic_quality.get("status"),
                "matched_rules": viability.get("matched_rules", []),
            },
            {"snippet": {"structural_contract": structural}},
            semantic_minimum,
        )
    )
    policy_mismatches = selection_policy_mismatches(structural)
    ready = [
        row for row in list(dependency_profile.get("ranked_alternatives") or [])
        if isinstance(row, dict) and row.get("readiness_status") == "ready" and ":" in str(row.get("target") or "")
    ]
    controlled_probe_allowed = _controlled_acceptance_probe_allowed(
        extraction_contract, dependency_profile, viability_blocked=viability_blocked
    )
    if not semantic_block and not source_unbound and not source_context_blocked and not viability_blocked and not semantic_below_threshold and not policy_mismatches and (
        dependency_profile.get("status") != "resolution_required" or ready or controlled_probe_allowed
    ):
        return {
            "artifact_type": "FirstSliceReselectionRequest",
            "status": "not_required",
            "current_target": extraction_contract.get("candidate"),
        }
    policy = dict(load_technical_spec_policy().get("dependency_readiness") or {})
    trigger = "no_semantically_safe_candidate_in_approved_first_slice" if semantic_block else (
        "source_body_not_bound_in_approved_first_slice" if source_unbound
        else "low_first_slice_viability" if viability_blocked
        else "first_slice_semantic_quality_below_threshold" if semantic_below_threshold
        else "promoted_selection_policy_mismatch" if policy_mismatches
        else "no_environment_ready_candidate_in_approved_first_slice"
    )
    return {
        "artifact_type": "FirstSliceReselectionRequest",
        "status": "required",
        "current_target": extraction_contract.get("candidate"),
        "trigger": trigger,
        "blocking_evidence": {
            "missing_modules": list(dependency_profile.get("missing_modules") or []),
            "ranked_alternatives": list(dependency_profile.get("ranked_alternatives") or []),
            "rejected_candidates": list(extraction_contract.get("ranked_candidates") or []),
            "structural_evidence": structural,
            "first_slice_viability": viability,
            "semantic_quality": semantic_quality,
            "minimum_semantic_score": semantic_minimum,
            "acceptance_signal": "meta_only" if policy_mismatches else None,
            "selection_policy_mismatches": policy_mismatches,
        },
        "required_candidate_properties": list(policy.get("reselection_required_properties") or []),
        "authority": "architect_reselection_required_no_automatic_scope_expansion",
        "forbidden_actions": ["expand_writable_scope", "install_dependency", "select_unproven_symbol"],
        "next_step": "return_to_architect_and_rebuild_technical_spec",
    }


def _controlled_acceptance_probe_allowed(
    extraction_contract: dict[str, Any],
    dependency_profile: dict[str, Any],
    *,
    viability_blocked: bool,
) -> bool:
    if dependency_profile.get("status") != "resolution_required" or viability_blocked:
        return False
    target = str(extraction_contract.get("candidate") or "")
    structural = dict(extraction_contract.get("structural_evidence") or {})
    viability = dict(extraction_contract.get("first_slice_viability") or {})
    viability_rules = {
        str(row.get("rule_id") or "")
        for row in viability.get("matched_rules") or []
        if isinstance(row, dict)
    }
    missing = [str(item) for item in dependency_profile.get("missing_modules") or [] if item]
    stubs = dependency_stub_policy()
    return bool(
        ":" in target
        and "declared_protocol_input" in viability_rules
        and structural.get("source_body_complete") is True
        and missing
        and stubs.get("enabled")
        and stubs.get("stub_external_missing_modules")
        and len(missing) <= int(stubs.get("max_missing_modules") or 0)
    )
