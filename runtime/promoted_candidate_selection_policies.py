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
        if signal in {str(item) for item in row.get("trigger_signals") or []}
    ]
    if not policies:
        return ranked
    preferred = [row for row in ranked if any(candidate_matches_policy(row, policy) for policy in policies)]
    if not preferred:
        return ranked
    preferred_ids = {id(row) for row in preferred}
    for row in preferred:
        row["selection_policy_ids"] = sorted({
            str(policy["id"]) for policy in policies if candidate_matches_policy(row, policy)
        })
    return [*preferred, *[row for row in ranked if id(row) not in preferred_ids]]


def candidate_matches_policy(candidate: dict[str, Any], policy: dict[str, Any]) -> bool:
    required = dict(policy.get("structural_requirements") or {})
    if int(candidate.get("return_paths") or 0) < int(required.get("min_return_paths") or 0):
        return False
    if required.get("state_mutation") is False and bool(candidate.get("state_mutation")):
        return False
    forbidden = {str(item) for item in required.get("forbidden_output_inference_basis") or []}
    if str(candidate.get("output_inference_basis") or "") in forbidden:
        return False
    minimum_typed = int(required.get("min_typed_argument_count") or 0)
    return int(candidate.get("typed_argument_count") or 0) >= minimum_typed


def promote_selection_policy(
    *, root: Path, policy: dict[str, Any], promotion_evidence: dict[str, Any]
) -> dict[str, Any]:
    path = root / "knowledge" / "role_knowledge" / "promoted_candidate_selection_policies.json"
    payload = load_selection_policies(str(path))
    policy_id = str(policy.get("id") or "")
    if any(str(row.get("id")) == policy_id for row in payload["policies"]):
        return {"status": "already_promoted", "policy_id": policy_id, "path": path.as_posix()}
    record = {**policy, "promotion_evidence": promotion_evidence, "numeric_bonus": False}
    candidate = {**payload, "policies": sorted([*payload["policies"], record], key=lambda row: str(row["id"]))}
    _validate_candidate(candidate)
    _atomic_write(path, candidate)
    load_selection_policies.cache_clear()
    return {"status": "promoted", "policy_id": policy_id, "path": path.as_posix()}


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
