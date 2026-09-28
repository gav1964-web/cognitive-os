"""Keep current-project evidence out of candidate-selection training families."""

from __future__ import annotations

from typing import Any

from runtime.promoted_candidate_selection_policies import load_selection_policies


def partition_holdout_project(
    groups: list[dict[str, Any]], project: str, failure_class: str = "",
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    training = []
    holdout = []
    for group in groups:
        retained = []
        retained_projects: set[str] = set()
        records = list(group.get("records") or [])
        if not records:
            training.append(group)
            continue
        for value in records:
            record = dict(value)
            confirmed = set(record.get("_confirmed_projects") or [])
            if project in confirmed:
                holdout.append({"group_id": str(group["id"]), **record})
            remaining = confirmed - {project}
            if remaining:
                record["_confirmed_projects"] = sorted(remaining)
                retained.append(record)
                retained_projects.update(remaining)
        if retained:
            training.append({
                **group,
                "records": retained,
                "projects": retained_projects,
            })
    if not failure_class:
        return training, holdout
    training = [
        group for group in training
        if str(group["id"]).split(":", 1)[0] == failure_class
    ]
    holdout = [
        record for record in holdout
        if str(record["group_id"]).split(":", 1)[0] == failure_class
    ]
    return training, holdout


def holdout_contrast_matches(
    records: list[dict[str, Any]], family_id: str, policy: dict[str, Any], matcher,
) -> bool:
    base_id = family_id.split(":structural_", 1)[0]
    return any(
        str(record.get("group_id")) == base_id
        and matcher(
            dict(record.get("failed_contract") or {}),
            dict(record.get("successful_contract") or {}),
            policy,
        )
        for record in records
    )


def contrast_evidence_matches(
    records: list[dict[str, Any]], family_id: str, policy: dict[str, Any],
    control: dict[str, Any], treatment: dict[str, Any], matcher,
) -> bool:
    return holdout_contrast_matches(records, family_id, policy, matcher) or matcher(
        control, treatment, policy,
    )


def inactive_legacy_families(root, failure_class: str) -> list[dict[str, Any]]:
    families = []
    path = root / "knowledge/role_knowledge/promoted_candidate_selection_policies.json"
    if not path.is_file():
        return families
    for value in load_selection_policies(str(path))["policies"]:
        policy = _repair_legacy_preflight(dict(value))
        if policy.get("activation_state") in {"active", "reproduction_trial"}:
            continue
        if failure_class and str(policy["id"]).split(":", 1)[0] != failure_class:
            continue
        evidence = dict(policy.get("promotion_evidence") or {})
        projects = {str(item) for item in evidence.get("confirmed_projects") or []}
        if projects and evidence.get("holdout_project"):
            families.append({
                "id": str(policy["id"]), "projects": projects,
                "records": [], "policy": policy,
            })
    return families


def _repair_legacy_preflight(policy: dict[str, Any]) -> dict[str, Any]:
    requirements = dict(policy.get("structural_requirements") or {})
    forbidden = {str(value) for value in requirements.get("forbidden_output_inference_basis") or []}
    preflight = dict(policy.get("preflight_trigger_requirements") or {})
    outputs = {str(value) for value in preflight.get("output_inference_basis") or []}
    missing = forbidden - outputs
    if not missing:
        return policy
    preflight["output_inference_basis"] = sorted(outputs | missing)
    return {
        **policy, "preflight_trigger_requirements": preflight,
        "legacy_revalidation_repairs": ["include_forbidden_output_in_preflight"],
    }
