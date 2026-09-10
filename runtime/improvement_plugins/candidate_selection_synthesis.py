"""Synthesize shared structural discriminators from heterogeneous contrasts."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def synthesized_discriminator_families(
    groups: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Aggregate atomic separators even when complete policies differ."""
    families: dict[tuple[str, str], dict[str, Any]] = {}
    for group in groups:
        base_id = str(group["id"])
        for record in group.get("records") or []:
            for policy in _atomic_policies(base_id, dict(record)):
                signature = _policy_signature(policy)
                key = (base_id, signature)
                family = families.setdefault(key, {
                    "id": "", "records": [], "projects": set(), "policy": policy,
                    "synthesis": "shared_atomic_structural_discriminator",
                })
                family["records"].append(record)
                family["projects"].update(record.get("_confirmed_projects") or [])
    result = []
    for (base_id, signature), family in families.items():
        suffix = hashlib.sha256(signature.encode("utf-8")).hexdigest()[:10]
        family_id = f"{base_id}:synthesized_{suffix}"
        family["id"] = family_id
        family["policy"] = {**family["policy"], "id": family_id}
        result.append(family)
    return sorted(
        result,
        key=lambda row: (-len(row["projects"]), -_specificity(row["policy"]), row["id"]),
    )


def _atomic_policies(base_id: str, record: dict[str, Any]) -> list[dict[str, Any]]:
    failed = dict(record.get("failed_contract") or {})
    successful = dict(record.get("successful_contract") or {})
    signal = str(failed.get("acceptance_signal") or "meta_only")
    atoms: list[tuple[dict[str, Any], dict[str, Any]]] = []
    failed_effects = {str(value) for value in failed.get("observed_side_effects") or []}
    successful_effects = {
        str(value) for value in successful.get("observed_side_effects") or []
    }
    if failed_effects and not successful_effects:
        atoms.append((
            {"no_observed_side_effects": True}, {"observed_side_effects": "nonempty"},
        ))
    else:
        for effect in sorted(failed_effects - successful_effects):
            atoms.append((
                {"forbidden_observed_side_effects": [effect]},
                {"required_observed_side_effects": [effect]},
            ))
    failed_output = str(failed.get("output_inference_basis") or "")
    successful_output = str(successful.get("output_inference_basis") or "")
    if failed_output and successful_output and failed_output != successful_output:
        atoms.append((
            {"forbidden_output_inference_basis": [failed_output]},
            {"output_inference_basis": [failed_output]},
        ))
    if failed.get("literal_return_only") is True and successful.get("literal_return_only") is False:
        atoms.append(({"literal_return_only": False}, {"literal_return_only": True}))
    failed_returns = int(failed.get("return_paths") or 0)
    successful_returns = int(successful.get("return_paths") or 0)
    if failed_returns == 0 and successful_returns > 0 and failed_output:
        atoms.append((
            {"min_return_paths": 1}, {"output_inference_basis": [failed_output]},
        ))
    _append_numeric_separator(
        atoms, failed, successful, "argument_count",
        maximum_key="max_argument_count", minimum_trigger="min_argument_count",
    )
    failed_usage = len(dict(failed.get("argument_usage_types") or {}))
    successful_usage = len(dict(successful.get("argument_usage_types") or {}))
    if successful_usage > failed_usage:
        atoms.append((
            {"min_argument_usage_count": successful_usage},
            {"max_argument_usage_count": failed_usage},
        ))
    failed_costs = {
        str(value) for value in failed.get("execution_cost_rules") or []
    }
    successful_costs = {
        str(value) for value in successful.get("execution_cost_rules") or []
    }
    for cost in sorted(failed_costs - successful_costs):
        atoms.append((
            {"forbidden_ranking_reason_tokens": [cost]},
            {"any_ranking_reason_tokens": [cost]},
        ))
    failed_dependency = str(failed.get("dependency_status") or "")
    successful_dependency = str(successful.get("dependency_status") or "")
    if (
        failed_dependency not in {"", "unknown"}
        and successful_dependency not in {"", "unknown", failed_dependency}
    ):
        atoms.append((
            {"forbidden_dependency_status": [failed_dependency]},
            {"dependency_status": [failed_dependency]},
        ))
    return [_policy(base_id, signal, required, trigger) for required, trigger in atoms]


def _append_numeric_separator(
    atoms: list[tuple[dict[str, Any], dict[str, Any]]],
    failed: dict[str, Any], successful: dict[str, Any], field: str,
    *, maximum_key: str, minimum_trigger: str,
) -> None:
    failed_value = int(failed.get(field) or 0)
    successful_value = int(successful.get(field) or 0)
    if successful_value < failed_value:
        atoms.append((
            {maximum_key: successful_value}, {minimum_trigger: failed_value},
        ))


def _policy(
    base_id: str, signal: str, required: dict[str, Any], trigger: dict[str, Any],
) -> dict[str, Any]:
    return {
        "id": base_id,
        "trigger": "executable_acceptance_rejected",
        "trigger_signals": [signal],
        "structural_requirements": required,
        "selection_mode": "stable_partition_existing_candidates",
        "candidate_ordering": "executable_fixture_readiness",
        "preflight_trigger_requirements": trigger,
        "numeric_bonus": False,
    }


def _policy_signature(policy: dict[str, Any]) -> str:
    return json.dumps({
        "trigger_signals": policy["trigger_signals"],
        "structural_requirements": policy["structural_requirements"],
        "preflight_trigger_requirements": policy["preflight_trigger_requirements"],
    }, sort_keys=True, separators=(",", ":"))


def _specificity(policy: dict[str, Any]) -> int:
    return len(dict(policy.get("structural_requirements") or {}))
