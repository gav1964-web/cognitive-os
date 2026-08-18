"""Validate an explicit, source-bound contract profile requested by Architect."""

from __future__ import annotations

from typing import Any

from .contract_transform_contract_profiles import contract_profile_for_operator


def bind_requested_contract_profile(
    architecture_decision: dict[str, Any],
    extraction_contract: dict[str, Any],
) -> dict[str, Any]:
    brief = dict(architecture_decision.get("spec_writer_brief") or {})
    requested = dict(brief.get("requested_contract_profile") or {})
    operator_id = str(requested.get("operator_id") or "")
    profile_id = str(requested.get("id") or "")
    target = _single_target(brief)
    goal = str(architecture_decision.get("goal") or "")
    source = dict(dict(architecture_decision.get("source_context") or {}).get(target) or {})
    profile = dict(contract_profile_for_operator(operator_id) or {})
    if not _valid_request(profile, profile_id, operator_id, target, goal, source):
        return extraction_contract
    signature = dict(source.get("signature") or {})
    args = [dict(row) for row in list(signature.get("args") or []) if isinstance(row, dict)]
    arg_name = str(args[0].get("name") or "value")
    input_types = [str(item) for item in list(profile.get("input_types") or []) if item]
    output_types = [str(item) for item in list(profile.get("output_types") or []) if item]
    ranked = list(extraction_contract.get("ranked_candidates") or [])
    score = next((int(row.get("score") or 0) for row in ranked if row.get("source") == target), 100)
    return {
        **extraction_contract,
        "status": "ready",
        "candidate": target,
        "candidate_score": max(score, 100),
        "selection_reason": "explicit source-bound contract profile request",
        "input_contract": {arg_name: input_types[0] if input_types else "InferredInput"},
        "output_contract": {"result": output_types[0] if output_types else "InferredOutput"},
        "side_effects": {
            "declared": [],
            "requires_process_boundary": False,
            "idempotency_required": False,
        },
        "evidence_source": target,
        "contract_profile": {
            "id": profile_id,
            "operator_id": operator_id,
            "source": "contract_transform_contract_profiles",
        },
        "requested_profile_binding": {
            "status": "verified",
            "authority": "explicit_architect_request_plus_source_signature_plus_kb_profile",
            "evidence": requested.get("evidence"),
        },
    }


def _valid_request(
    profile: dict[str, Any],
    profile_id: str,
    operator_id: str,
    target: str,
    goal: str,
    source: dict[str, Any],
) -> bool:
    if not profile or profile.get("id") != profile_id or profile.get("operator_id") != operator_id:
        return False
    if not target or f"verified {operator_id}" not in goal.lower():
        return False
    args = [row for row in list(dict(source.get("signature") or {}).get("args") or []) if isinstance(row, dict)]
    snippet = dict(source.get("snippet") or {}).get("text")
    return len(args) == 1 and bool(args[0].get("name")) and bool(snippet)


def _single_target(brief: dict[str, Any]) -> str:
    targets = [str(item) for item in list(brief.get("files_or_symbols") or []) if item]
    return targets[0] if len(targets) == 1 else ""
