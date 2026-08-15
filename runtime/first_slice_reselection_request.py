"""Architect handoff when an approved first slice has no executable target."""

from __future__ import annotations

from typing import Any

from .technical_spec_policy import load_technical_spec_policy


def build_first_slice_reselection_request(
    extraction_contract: dict[str, Any], dependency_profile: dict[str, Any]
) -> dict[str, Any]:
    ready = [
        row for row in list(dependency_profile.get("ranked_alternatives") or [])
        if isinstance(row, dict) and row.get("readiness_status") == "ready" and ":" in str(row.get("target") or "")
    ]
    if dependency_profile.get("status") != "resolution_required" or ready:
        return {
            "artifact_type": "FirstSliceReselectionRequest",
            "status": "not_required",
            "current_target": extraction_contract.get("candidate"),
        }
    policy = dict(load_technical_spec_policy().get("dependency_readiness") or {})
    return {
        "artifact_type": "FirstSliceReselectionRequest",
        "status": "required",
        "current_target": extraction_contract.get("candidate"),
        "trigger": "no_environment_ready_candidate_in_approved_first_slice",
        "blocking_evidence": {
            "missing_modules": list(dependency_profile.get("missing_modules") or []),
            "ranked_alternatives": list(dependency_profile.get("ranked_alternatives") or []),
        },
        "required_candidate_properties": list(policy.get("reselection_required_properties") or []),
        "authority": "architect_reselection_required_no_automatic_scope_expansion",
        "forbidden_actions": ["expand_writable_scope", "install_dependency", "select_unproven_symbol"],
        "next_step": "return_to_architect_and_rebuild_technical_spec",
    }
