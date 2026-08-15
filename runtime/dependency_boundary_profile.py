"""Formal dependency-boundary evidence for a selected extraction target."""

from __future__ import annotations

from typing import Any

from .technical_spec_policy import load_technical_spec_policy
from .isolated_dependency_profile import build_isolated_dependency_profile


def build_dependency_boundary_profile(
    extraction_contract: dict[str, Any], *, project_root: str | None = None
) -> dict[str, Any]:
    readiness = dict(extraction_contract.get("dependency_readiness") or {})
    missing = [str(item) for item in list(readiness.get("missing_external_modules") or []) if item]
    if not missing:
        return {
            "artifact_type": "DependencyBoundaryProfile",
            "status": "not_required",
            "target": extraction_contract.get("candidate"),
            "missing_modules": [],
        }
    policy = dict(load_technical_spec_policy().get("dependency_readiness") or {})
    profile = {
        "artifact_type": "DependencyBoundaryProfile",
        "status": "resolution_required",
        "target": extraction_contract.get("candidate"),
        "missing_modules": missing,
        "import_graph_evidence": {
            "analysis": readiness.get("analysis"),
            "local_modules_scanned": readiness.get("local_modules_scanned"),
            "local_imports": list(readiness.get("local_imports") or []),
            "external_imports": list(readiness.get("external_imports") or []),
        },
        "ranked_alternatives": _ranked_alternatives(extraction_contract),
        "resolution_options": list(policy.get("profile_resolution_options") or []),
        "verification_gates": list(policy.get("profile_verification_gates") or []),
        "forbidden_actions": list(policy.get("profile_forbidden_actions") or []),
        "authority": "advisory_environment_boundary_no_install_or_source_mutation",
        "next_step": "resolve_environment_or_reselect_first_slice_then_rebuild_downstream_artifacts",
    }
    profile["isolated_environment_profile"] = build_isolated_dependency_profile(
        project_root=project_root,
        target=str(extraction_contract.get("candidate") or ""),
        missing_modules=missing,
    )
    return profile


def _ranked_alternatives(extraction_contract: dict[str, Any]) -> list[dict[str, Any]]:
    selected = str(extraction_contract.get("candidate") or "")
    rows = []
    for item in list(extraction_contract.get("ranked_candidates") or []):
        if not isinstance(item, dict) or str(item.get("source") or "") == selected:
            continue
        readiness = dict(item.get("dependency_readiness") or {})
        rows.append({
            "target": item.get("source"),
            "score": item.get("score"),
            "readiness_status": readiness.get("status") or "unknown",
            "missing_modules": list(readiness.get("missing_external_modules") or []),
        })
    return rows[:8]
