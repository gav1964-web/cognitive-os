from __future__ import annotations

from typing import Any
from runtime.source_contract_types import all_contract_shapes_concrete
from runtime.technical_spec_policy import load_technical_spec_policy

TECHNICAL_SPEC_POLICY = load_technical_spec_policy()


def _semantic_contract_proven(contract: dict[str, Any], quality: dict[str, Any]) -> bool:
    structural = dict(contract.get("structural_evidence") or {})
    effects = dict(contract.get("side_effects") or {})
    minimum = int(dict(TECHNICAL_SPEC_POLICY.get("first_slice_reselection") or {}).get("minimum_semantic_score") or 100)
    return bool(
        int(quality.get("score") or 0) >= minimum
        and structural.get("source_body_complete") is True
        and structural.get("state_mutation") is not True
        and all_contract_shapes_concrete(
            dict(contract.get("input_contract") or {}), dict(contract.get("output_contract") or {})
        )
        and not list(effects.get("declared") or [])
    )


def _spec_traceability(
    traceability: list[dict[str, Any]],
    acceptance: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows = []
    by_source = _acceptance_by_source(acceptance)
    fallback_ids = [str(row.get("id") or "") for row in acceptance if isinstance(row, dict)]
    for index, row in enumerate(traceability[: len(acceptance)]):
        source = str(row.get("source") or "")
        rows.append(
            {
                "source": row.get("source"),
                "requirement": row.get("requirement"),
                "acceptance_id": by_source.get(source) or fallback_ids[min(index, len(fallback_ids) - 1)] if fallback_ids else None,
            }
        )
    return rows

def _acceptance_by_source(acceptance: list[dict[str, Any]]) -> dict[str, str]:
    result = {}
    for row in acceptance:
        if not isinstance(row, dict):
            continue
        source = str(row.get("source") or "")
        item_id = str(row.get("id") or "")
        if source and item_id and source not in result:
            result[source] = item_id
    return result

def _bounded_read_only_ranked_context(scoped: list[dict[str, Any]], ranked: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not scoped:
        return scoped
    seen = {str(item.get("source") or "") for item in scoped}
    context = []
    limit = max(0, int(dict(TECHNICAL_SPEC_POLICY.get("first_slice_scope") or {}).get("read_only_ranked_context_limit", 12)))
    for item in ranked:
        source = str(item.get("source") or "")
        learned_context = bool(item.get("selection_policy_ids"))
        if not source or source in seen:
            continue
        row = dict(item)
        reason = (
            "learned policy candidate retained as read-only context"
            if learned_context
            else "ranked candidate retained as read-only context after first-slice scope enforcement"
        )
        row["reasons"] = [*list(row.get("reasons", [])), reason]
        context.append(row)
        seen.add(source)
        if len(context) >= limit:
            break
    return context


def _append_learned_ranked_context(
    scoped: list[dict[str, Any]], context: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    result = list(scoped)
    seen = {str(item.get("source") or "") for item in result}
    for item in context:
        source = str(item.get("source") or "")
        if source and source not in seen and item.get("selection_policy_ids"):
            result.append(item)
            seen.add(source)
    return result

def _semantic_review_override(contract: dict[str, Any], quality: dict[str, Any], preferred_targets: list[Any]) -> dict[str, Any]:
    policy = dict(TECHNICAL_SPEC_POLICY.get("semantic_review_override") or {})
    process_policy = dict(TECHNICAL_SPEC_POLICY.get("process_boundary_review_override") or {})
    if process_policy.get("enabled"):
        process_checks = _process_boundary_review_checks(contract, quality, preferred_targets, process_policy)
        if all(process_checks.values()):
            return {
                "status": str(process_policy.get("verdict") or "approved_with_constraints"),
                "checks": process_checks,
                "policy": "technical_spec_policy.process_boundary_review_override",
                "principle": "broad legacy boundaries may proceed only as isolated process/side-effect contracts",
            }
    if not policy.get("enabled"):
        return {"status": "not_applicable"}
    checks = _semantic_review_checks(contract, quality, preferred_targets, policy)
    verdict = str(policy.get("verdict") or "approved_with_constraints")
    return {
        "status": verdict if all(checks.values()) else "needs_human_review",
        "checks": checks,
        "policy": "technical_spec_policy.semantic_review_override",
        "principle": "suspicious helper targets may proceed only when first-slice evidence proves a bounded executable contract",
    }

def _semantic_review_checks(
    contract: dict[str, Any], quality: dict[str, Any], preferred_targets: list[Any], policy: dict[str, Any]
) -> dict[str, bool]:
    candidate = str(contract.get("candidate") or "")
    reason_text = " ".join([str(contract.get("selection_reason") or ""), *[str(r) for r in quality.get("reasons", [])]]).lower()
    preferred = {_normalize_source_ref(str(item)) for item in preferred_targets if item}
    required = [str(item).lower() for item in list(policy.get("required_reason_tokens") or []) if item]
    return {
        "status_allowed": str(quality.get("status") or "") in set(policy.get("allowed_statuses") or []),
        "not_explicitly_too_broad": "too broad" not in reason_text,
        "candidate_score_high_enough": int(contract.get("candidate_score") or 0) >= int(policy.get("min_candidate_score") or 0),
        "candidate_in_first_slice": not policy.get("required_candidate_in_first_slice", True) or candidate in preferred,
        "source_evidence_bound": bool(contract.get("evidence_source") == candidate),
        "io_contract_bound": bool(contract.get("input_contract") and contract.get("output_contract")),
        "no_side_effects": not bool(dict(contract.get("side_effects") or {}).get("declared")),
        "required_reason_tokens_present": all(token in reason_text for token in required),
    }

def _process_boundary_review_checks(
    contract: dict[str, Any], quality: dict[str, Any], preferred_targets: list[Any], policy: dict[str, Any]
) -> dict[str, bool]:
    candidate = str(contract.get("candidate") or "")
    preferred = {_normalize_source_ref(str(item)) for item in preferred_targets if item}
    profile_ids = {str(item) for item in list(quality.get("semantic_profile_ids") or [])}
    required_profiles = {str(item) for item in list(policy.get("required_profile_ids") or [])}
    side_effects = {str(item).lower() for item in list(dict(contract.get("side_effects") or {}).get("declared") or [])}
    required_effects = {str(item).lower() for item in list(policy.get("required_side_effects_any") or [])}
    reason_text = " ".join(str(reason) for reason in list(quality.get("reasons") or [])).lower()
    return {
        "status_allowed": str(quality.get("status") or "") in set(policy.get("allowed_statuses") or []),
        "required_profile_present": bool(profile_ids & required_profiles),
        "not_explicitly_too_broad": "too broad" not in reason_text,
        "candidate_in_first_slice": candidate in preferred,
        "source_evidence_bound": bool(contract.get("evidence_source") == candidate),
        "io_contract_bound": bool(contract.get("input_contract") and contract.get("output_contract")),
        "process_or_side_effect_boundary_declared": bool(side_effects & required_effects),
    }
