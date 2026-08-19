"""Architect handoff when an approved first slice has no executable target."""

from __future__ import annotations

from typing import Any

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
    explicit_return = str(structural.get("explicit_return_annotation") or "").strip().lower()
    fully_annotated = (
        explicit_return not in {"", "any", "typing.any", "object"}
        and int(structural.get("typed_argument_count") or 0) >= int(structural.get("argument_count") or 0)
    )
    semantic_below_threshold = (
        bool(extraction_contract.get("candidate") and semantic_quality)
        and semantic_score < semantic_minimum
        and not fully_annotated
    )
    ready = [
        row for row in list(dependency_profile.get("ranked_alternatives") or [])
        if isinstance(row, dict) and row.get("readiness_status") == "ready" and ":" in str(row.get("target") or "")
    ]
    if not semantic_block and not source_unbound and not source_context_blocked and not viability_blocked and not semantic_below_threshold and (
        dependency_profile.get("status") != "resolution_required" or ready
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
        },
        "required_candidate_properties": list(policy.get("reselection_required_properties") or []),
        "authority": "architect_reselection_required_no_automatic_scope_expansion",
        "forbidden_actions": ["expand_writable_scope", "install_dependency", "select_unproven_symbol"],
        "next_step": "return_to_architect_and_rebuild_technical_spec",
    }
