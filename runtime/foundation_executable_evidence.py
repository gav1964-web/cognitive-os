"""Conservative executable confirmation for foundation role handoffs."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from .executable_acceptance import run_executable_acceptance
from .executable_acceptance_process import run_executable_acceptance_process
from .executable_acceptance_policy import (
    effective_executable_acceptance_policy,
    foundation_evidence_policy,
)
from .implementation_plan_builder import build_implementation_plan
from .test_plan_builder import build_test_plan


def collect_foundation_executable_evidence(
    *, root: Path, project_dir: Path, technical_spec: dict[str, Any],
    process_isolated: bool = False, shadow_target: str | None = None,
) -> dict[str, Any]:
    eligibility = _eligibility(
        technical_spec, process_isolated=process_isolated, shadow_target=shadow_target,
    )
    if eligibility["status"] != "eligible":
        return eligibility
    implementation_plan = build_implementation_plan(technical_spec=technical_spec)
    test_plan = build_test_plan(
        technical_spec=technical_spec,
        implementation_plan=implementation_plan,
    )
    obligations = list(dict(test_plan.get("executable_acceptance") or {}).get("obligations") or [])
    if not obligations:
        return {**eligibility, "status": "skipped", "reason": "no_executable_obligations"}
    work_dir = _work_dir(root, project_dir, str(eligibility["target"]))
    if process_isolated:
        policy = foundation_evidence_policy()
        acceptance = run_executable_acceptance_process(
            root=root, project_dir=project_dir, test_plan=test_plan, work_dir=work_dir,
            timeout_seconds=int(policy["isolated_process_timeout_seconds"]),
            executable_policy=effective_executable_acceptance_policy(),
        )
    else:
        acceptance = run_executable_acceptance(
            root=root, project_dir=project_dir, test_plan=test_plan, work_dir=work_dir,
        )
    summary = dict(acceptance.get("summary") or {})
    signal = str(summary.get("signal_strength") or "") if acceptance.get("status") == "passed" else ""
    return {
        "status": str(acceptance.get("status") or "failed"),
        "target": eligibility["target"],
        "acceptance_signal": signal,
        "summary": summary,
        "result_path": acceptance.get("result_path"),
        "source_code_changes": acceptance.get("source_code_changes", False),
    }


def _eligibility(
    spec: dict[str, Any], *, process_isolated: bool = False,
    shadow_target: str | None = None,
) -> dict[str, Any]:
    contract = dict(spec.get("extraction_contract") or {})
    target = str(contract.get("candidate") or "")
    request = dict(spec.get("first_slice_reselection_request") or {})
    structural = dict(contract.get("structural_evidence") or {})
    effects = list(dict(contract.get("side_effects") or {}).get("declared") or [])
    direct_effects = list(structural.get("observed_side_effects") or [])
    evidence_policy = foundation_evidence_policy()
    isolated_effects = set(evidence_policy["isolated_transitive_effects"])
    effects_are_isolated_transitive = bool(effects) and not direct_effects and set(effects) <= isolated_effects
    process_direct_effects = set(evidence_policy["process_isolated_direct_effects"])
    effects_are_process_isolated_direct = (
        process_isolated
        and bool(direct_effects)
        and set(direct_effects) <= process_direct_effects
        and set(effects) <= process_direct_effects
    )
    archetypes = set(dict(contract.get("semantic_quality") or {}).get("contract_archetype_ids") or [])
    archetypes.add(str(contract.get("contract_family") or ""))
    profiles = dict(evidence_policy["isolated_direct_effect_profiles"])
    effects_are_isolated_direct = any(
        archetype in archetypes
        and bool(direct_effects)
        and set(direct_effects) <= set(allowed)
        and set(effects) <= set(allowed)
        for archetype, allowed in profiles.items()
    )
    process_profiles = dict(evidence_policy["process_isolated_direct_effect_profiles"])
    effects_are_profiled_process_direct = process_isolated and any(
        archetype in archetypes
        and bool(direct_effects)
        and set(direct_effects) <= set(allowed)
        and set(effects) <= set(allowed)
        for archetype, allowed in process_profiles.items()
    )
    delegated_profiles = dict(evidence_policy["isolated_delegated_effect_profiles"])
    effects_are_isolated_delegated = any(
        archetype in archetypes
        and not direct_effects
        and set(effects) <= set(allowed)
        for archetype, allowed in delegated_profiles.items()
    )
    shadow_admitted = _shadow_target_admitted(
        target=target,
        requested_target=shadow_target,
        request=request,
        structural=structural,
        effects=effects,
        direct_effects=direct_effects,
        process_isolated=process_isolated,
        policy=dict(evidence_policy["shadow_target_admission"]),
    )
    reason = ""
    if spec.get("artifact_type") != "TechnicalSpec":
        reason = "technical_spec_missing"
    elif request.get("status") == "required" and not shadow_admitted:
        reason = "first_slice_reselection_required"
    elif not target or contract.get("status") == "blocked_no_safe_candidate":
        reason = "safe_target_missing"
    elif effects and not (
        effects_are_isolated_transitive
        or effects_are_process_isolated_direct
        or effects_are_isolated_direct
        or effects_are_profiled_process_direct
        or effects_are_isolated_delegated
    ):
        reason = "side_effectful_target"
    elif structural.get("state_mutation") is True and not effects_are_process_isolated_direct:
        reason = "state_mutating_target"
    return {
        "status": "skipped" if reason else "eligible",
        "reason": reason or None,
        "target": target or None,
        "acceptance_signal": "",
        "shadow_target_admitted": shadow_admitted,
    }


def _shadow_target_admitted(
    *, target: str, requested_target: str | None, request: dict[str, Any],
    structural: dict[str, Any], effects: list[str], direct_effects: list[str],
    process_isolated: bool, policy: dict[str, Any],
) -> bool:
    if not policy.get("enabled") or not requested_target or target != requested_target:
        return False
    if request.get("status") != "required":
        return False
    if str(request.get("trigger") or "") not in set(policy["allowed_reselection_triggers"]):
        return False
    checks = (
        not policy.get("require_process_isolation") or process_isolated,
        not policy.get("require_complete_source_body") or (
            structural.get("source_body_available") is True
            and structural.get("source_body_complete") is True
        ),
        not policy.get("require_no_declared_effects") or not effects,
        not policy.get("require_no_direct_effects") or not direct_effects,
        not policy.get("require_no_state_mutation") or structural.get("state_mutation") is not True,
    )
    return all(checks)


def _work_dir(root: Path, project_dir: Path, target: str) -> Path:
    digest = hashlib.sha256(f"{project_dir.resolve()}:{target}".encode("utf-8")).hexdigest()[:12]
    return root / "artifacts" / "executable_acceptance" / "foundation" / f"{project_dir.name}-{digest}"
