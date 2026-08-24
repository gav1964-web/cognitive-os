"""Active structural policies learned from measured candidate contrasts."""

from __future__ import annotations

import json
import os
import tempfile
from functools import lru_cache
from pathlib import Path
from typing import Any


DEFAULT_PATH = Path(__file__).resolve().parents[1] / "knowledge" / "role_knowledge" / "promoted_candidate_selection_policies.json"


@lru_cache(maxsize=4)
def load_selection_policies(path: str | None = None) -> dict[str, Any]:
    payload = json.loads(Path(path or DEFAULT_PATH).read_text(encoding="utf-8"))
    if payload.get("schema_version") != "promoted_candidate_selection_policies.v1":
        raise ValueError("promoted candidate selection policies schema mismatch")
    policies = payload.get("policies")
    if not isinstance(policies, list):
        raise ValueError("promoted candidate selection policies must contain policies list")
    seen: set[str] = set()
    for value in policies:
        policy = dict(value or {})
        policy_id = str(policy.get("id") or "")
        if not policy_id or policy_id in seen or not policy.get("trigger_signals"):
            raise ValueError(f"invalid promoted candidate selection policy: {policy_id}")
        if policy.get("trigger") != "executable_acceptance_rejected":
            raise ValueError(f"invalid selection policy trigger: {policy_id}")
        if not dict(policy.get("structural_requirements") or {}):
            raise ValueError(f"selection policy lacks structural requirements: {policy_id}")
        if policy.get("numeric_bonus") not in {None, False, 0}:
            raise ValueError(f"numeric selection bonus is forbidden: {policy_id}")
        forbidden = set(dict(policy.get("structural_requirements") or {}).get(
            "forbidden_output_inference_basis") or [])
        preflight = set(dict(policy.get("preflight_trigger_requirements") or {}).get(
            "output_inference_basis") or [])
        if _policy_enabled(policy) and preflight and forbidden and not preflight & forbidden:
            raise ValueError(f"selection policy has unreachable output preflight: {policy_id}")
        seen.add(policy_id)
    return payload


def apply_selection_policies(
    ranked: list[dict[str, Any]], request: dict[str, Any], *, path: str | None = None
) -> list[dict[str, Any]]:
    if request.get("trigger") != "executable_acceptance_rejected":
        return ranked
    signal = str(dict(request.get("blocking_evidence") or {}).get("acceptance_signal") or "meta_only")
    policies = [
        dict(row) for row in load_selection_policies(path)["policies"]
        if _policy_enabled(row)
        and signal in {str(item) for item in row.get("trigger_signals") or []}
    ]
    if not policies:
        return ranked
    evidence = [{**_candidate_evidence(row), **row} for row in ranked]
    preferred = [
        (row, item) for row, item in zip(ranked, evidence)
        if any(candidate_matches_policy(row, policy) for policy in policies)
    ]
    if not preferred:
        return ranked
    if any(policy.get("candidate_ordering") == "executable_fixture_readiness" for policy in policies):
        preferred.sort(key=lambda pair: _fixture_readiness_rank(pair[0], pair[1]))
    preferred_rows = [row for row, _item in preferred]
    preferred_ids = {id(row) for row in preferred_rows}
    for row, item in preferred:
        row["selection_policy_ids"] = sorted({
            str(policy["id"]) for policy in policies if candidate_matches_policy(row, policy)
        })
    return [*preferred_rows, *[row for row in ranked if id(row) not in preferred_ids]]


def apply_preflight_selection_policies(
    ranked: list[dict[str, Any]], *, path: str | None = None
) -> list[dict[str, Any]]:
    """Apply learned contrasts before a predicted rejected candidate is selected."""
    if len(ranked) < 2:
        return ranked
    policies = _preflight_policies(path)
    if not policies:
        return ranked
    evidence = [_candidate_evidence(row) for row in ranked]
    applicable = [
        policy for policy in policies
        if _matches_preflight_trigger(evidence[0], policy)
        and not candidate_matches_policy(evidence[0], policy)
        and any(candidate_matches_policy(item, policy) for item in evidence[1:])
    ]
    if not applicable:
        return ranked
    preferred = [
        (row, item) for row, item in zip(ranked, evidence)
        if any(candidate_matches_policy(item, policy) for policy in applicable)
    ]
    if any(policy.get("candidate_ordering") == "executable_fixture_readiness" for policy in applicable):
        preferred.sort(key=lambda pair: _fixture_readiness_rank(pair[0], pair[1]))
    preferred_rows = [row for row, _item in preferred]
    preferred_ids = {id(row) for row in preferred_rows}
    for row, item in zip(ranked, evidence):
        matched = [
            str(policy["id"]) for policy in applicable
            if candidate_matches_policy(item, policy)
        ]
        if matched:
            row["selection_policy_ids"] = sorted(matched)
    return [*preferred_rows, *[row for row in ranked if id(row) not in preferred_ids]]


def _fixture_readiness_rank(row: dict[str, Any], evidence: dict[str, Any]) -> tuple[int, int, int, str]:
    output = str(
        evidence.get("explicit_return_annotation")
        or evidence.get("inferred_output_type") or ""
    ).lower()
    simple = any(token in output for token in (
        "bool", "bytes", "dict", "float", "int", "list", "mapping",
        "number", "scalar", "sequence", "set", "str", "tuple",
    ))
    return (
        int(not simple),
        int(evidence.get("argument_count") or 0),
        -int(evidence.get("return_paths") or 0),
        str(row.get("source") or ""),
    )


def selection_policy_mismatches(candidate: dict[str, Any], *, path: str | None = None) -> list[str]:
    return sorted(
        str(policy["id"]) for policy in _preflight_policies(path)
        if _matches_preflight_trigger(candidate, policy)
        and not candidate_matches_policy(candidate, policy)
    )


def _preflight_policies(path: str | None) -> list[dict[str, Any]]:
    return [
        dict(row) for row in load_selection_policies(path)["policies"]
        if _policy_enabled(row)
        and row.get("selection_mode") == "stable_partition_existing_candidates"
        and "meta_only" in {str(item) for item in row.get("trigger_signals") or []}
        and dict(row.get("preflight_trigger_requirements") or {})
    ]


def _policy_enabled(policy: dict[str, Any]) -> bool:
    return policy.get("activation_state") in {"active", "reproduction_trial"}


def _matches_preflight_trigger(candidate: dict[str, Any], policy: dict[str, Any]) -> bool:
    required = dict(policy.get("preflight_trigger_requirements") or {})
    if required.get("literal_return_only") is True and not candidate.get("literal_return_only"):
        return False
    effects = list(candidate.get("observed_side_effects") or [])
    if required.get("observed_side_effects") == "nonempty" and not effects:
        return False
    required_effects = {str(value) for value in required.get("required_observed_side_effects") or []}
    if required_effects and not required_effects.intersection(str(value) for value in effects):
        return False
    forbidden = {str(value) for value in required.get("forbidden_observed_side_effects") or []}
    if forbidden & {str(value) for value in effects}:
        return False
    outputs = {str(value) for value in required.get("output_inference_basis") or []}
    return not outputs or str(candidate.get("output_inference_basis") or "") in outputs


def _candidate_evidence(row: dict[str, Any]) -> dict[str, Any]:
    from .source_contract_semantics import infer_source_contract

    source = dict(row.get("evidence") or row)
    inferred = infer_source_contract(source)
    effects = sorted({
        str(value) for value in [
            *list(row.get("side_effects") or []),
            *list(source.get("side_effects") or []),
            *list(inferred.get("observed_side_effects") or []),
        ] if value
    })
    return {**source, **inferred, "observed_side_effects": effects}


def candidate_matches_policy(candidate: dict[str, Any], policy: dict[str, Any]) -> bool:
    required = dict(policy.get("structural_requirements") or {})
    if int(candidate.get("return_paths") or 0) < int(required.get("min_return_paths") or 0):
        return False
    if required.get("state_mutation") is False and bool(candidate.get("state_mutation")):
        return False
    if required.get("literal_return_only") is False and bool(candidate.get("literal_return_only")):
        return False
    forbidden = {str(item) for item in required.get("forbidden_output_inference_basis") or []}
    if str(candidate.get("output_inference_basis") or "") in forbidden:
        return False
    if required.get("no_observed_side_effects") is True and candidate.get("observed_side_effects"):
        return False
    forbidden_effects = {str(item) for item in required.get("forbidden_observed_side_effects") or []}
    if forbidden_effects & {str(item) for item in candidate.get("observed_side_effects") or []}:
        return False
    minimum_typed = int(required.get("min_typed_argument_count") or 0)
    return int(candidate.get("typed_argument_count") or 0) >= minimum_typed


def contrast_matches_policy(
    failed: dict[str, Any], successful: dict[str, Any], policy: dict[str, Any]
) -> bool:
    return (
        _matches_preflight_trigger(failed, policy)
        and not candidate_matches_policy(failed, policy)
        and candidate_matches_policy(successful, policy)
    )


def promote_selection_policy(
    *, root: Path, policy: dict[str, Any], promotion_evidence: dict[str, Any]
) -> dict[str, Any]:
    path = root / "knowledge" / "role_knowledge" / "promoted_candidate_selection_policies.json"
    payload = load_selection_policies(str(path))
    policy_id = str(policy.get("id") or "")
    existing = next((dict(row) for row in payload["policies"] if str(row.get("id")) == policy_id), None)
    if existing and _policy_enabled(existing):
        return {"status": "already_promoted", "policy_id": policy_id, "path": path.as_posix()}
    record = {
        **policy,
        "activation_state": policy.get("activation_state") or "active",
        "promotion_evidence": promotion_evidence,
        "numeric_bonus": False,
    }
    retained = [row for row in payload["policies"] if str(row.get("id")) != policy_id]
    candidate = {**payload, "policies": sorted([*retained, record], key=lambda row: str(row["id"]))}
    _validate_candidate(candidate)
    _atomic_write(path, candidate)
    load_selection_policies.cache_clear()
    return {
        "status": "promoted", "policy_id": policy_id, "path": path.as_posix(),
        **({"legacy_revalidation": True} if existing else {}),
    }


def activate_selection_policy(root: Path, policy_id: str) -> dict[str, Any]:
    path = root / "knowledge" / "role_knowledge" / "promoted_candidate_selection_policies.json"
    payload = load_selection_policies(str(path))
    changed = False
    policies = []
    for value in payload["policies"]:
        row = dict(value)
        if str(row.get("id")) == policy_id:
            evidence = dict(row.get("promotion_evidence") or {})
            evidence["ordinary_route_reproduction"] = "passed"
            row.update({"activation_state": "active", "promotion_evidence": evidence})
            changed = True
        policies.append(row)
    if not changed:
        return {"status": "not_found", "policy_id": policy_id}
    _atomic_write(path, {**payload, "policies": policies})
    load_selection_policies.cache_clear()
    return {"status": "activated", "policy_id": policy_id, "path": path.as_posix()}


def _validate_candidate(payload: dict[str, Any]) -> None:
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False) as handle:
        json.dump(payload, handle, ensure_ascii=False)
        temporary = Path(handle.name)
    try:
        load_selection_policies.cache_clear()
        load_selection_policies(str(temporary))
    finally:
        temporary.unlink(missing_ok=True)


def _atomic_write(path: Path, payload: dict[str, Any]) -> None:
    encoded = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        handle.write(encoded)
        temporary = Path(handle.name)
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
