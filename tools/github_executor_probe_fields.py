"""Field extraction helpers for the GitHub Executor probe."""

from __future__ import annotations

from typing import Any


def contract_profile_fields(
    spec: dict[str, Any], plan: dict[str, Any], test_plan: dict[str, Any]
) -> dict[str, Any]:
    extraction = dict(spec.get("extraction_contract") or {})
    readiness = dict(extraction.get("dependency_readiness") or {})
    spec_profile = dict(extraction.get("contract_profile") or {})
    plan_profile = dict(dict(plan.get("contract_binding") or {}).get("contract_profile") or {})
    test_profile = _first_test_plan_profile(test_plan)
    profile = test_profile or plan_profile or spec_profile
    return {
        "contract_profile_id": str(profile.get("id") or ""),
        "contract_profile_operator_id": str(profile.get("operator_id") or ""),
        "contract_profile_source": str(profile.get("source") or ("test_plan" if test_profile else "")),
        "dependency_readiness_status": str(readiness.get("status") or "unknown"),
        "dependency_missing_modules": [str(item) for item in list(readiness.get("missing_external_modules") or [])],
    }


def strategy_fields(strategy: dict[str, Any]) -> dict[str, Any]:
    deterministic = dict(strategy.get("deterministic_strategy") or {})
    llm = dict(strategy.get("llm_strategy") or {})
    candidate = dict(strategy.get("sandbox_patch_candidate") or {})
    playbooks = _ids(strategy.get("executor_playbooks"))
    patterns = _ids(strategy.get("solution_patterns"))
    rebind = dict(strategy.get("contract_rebind_request") or {})
    dependency = dict(strategy.get("dependency_boundary_profile") or {})
    isolated = dict(dependency.get("isolated_environment_profile") or {})
    reselection = dict(strategy.get("first_slice_reselection_request") or {})
    return {
        "strategy_action": str(deterministic.get("action") or ""),
        "strategy_reason": str(deterministic.get("reason") or ""),
        "executor_playbook_ids": playbooks,
        "solution_pattern_ids": patterns,
        "llm_strategy_status": str(llm.get("status") or "none"),
        "sandbox_candidate_status": str(candidate.get("status") or "none"),
        "contract_rebind_requested": bool(rebind),
        "contract_rebind_reason": str(rebind.get("reason") or ""),
        "contract_rebind_candidates": [
            str(row.get("target") or "")
            for row in list(rebind.get("candidate_targets") or [])
            if isinstance(row, dict) and row.get("target")
        ],
        "dependency_profile_status": str(dependency.get("status") or "none"),
        "dependency_profile_missing_modules": [str(item) for item in list(dependency.get("missing_modules") or [])],
        "isolated_dependency_profile_status": str(isolated.get("status") or "none"),
        "first_slice_reselection_status": str(reselection.get("status") or "none"),
        "first_slice_reselection_resolution_status": str(reselection.get("resolution_status") or "none"),
    }


def _first_test_plan_profile(test_plan: dict[str, Any]) -> dict[str, Any]:
    obligations = list(dict(test_plan.get("executable_acceptance") or {}).get("obligations") or [])
    for obligation in obligations:
        profile = dict(obligation.get("contract_profile") or {}) if isinstance(obligation, dict) else {}
        if profile:
            return profile
    return {}


def _ids(value: Any) -> list[str]:
    return [str(row.get("id")) for row in list(value or []) if isinstance(row, dict) and row.get("id")]
