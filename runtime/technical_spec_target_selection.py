from __future__ import annotations

from typing import Any

from runtime.architecture_target_priority import (
    architecture_contract_has_priority,
    architecture_target_score,
    complete_architecture_contract,
)
from runtime.source_contract_semantics import infer_source_contract
from runtime.spec_writer_target_binding import standalone_target_eligibility
from runtime.technical_spec_domain_contract import domain_extraction_contract
from runtime.technical_spec_policy import load_technical_spec_policy


TECHNICAL_SPEC_POLICY = load_technical_spec_policy()
FIRST_SLICE_SCOPE_POLICY = dict(TECHNICAL_SPEC_POLICY.get("first_slice_scope") or {})


def normalize_source_ref(source: str) -> str:
    return source.replace("\\", "/")


def binding_rejection_rows(ranked: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for item in ranked[:12]:
        eligibility = standalone_target_eligibility(dict(item.get("evidence") or {}))
        rows.append({
            "source": item.get("source"),
            "target_binding": item.get("target_binding"),
            "reason": eligibility["reason"],
            "reason_code": item.get("blocked_reason"),
        })
    return rows


def reconciled_input_contract(
    signature_contract: dict[str, str], domain_contract: dict[str, Any], bindings: dict[str, Any] | None = None
) -> dict[str, str]:
    from runtime.contract_input_reconciliation import reconcile_input_contract

    return reconcile_input_contract(signature_contract, domain_contract, bindings)


def promote_preferred_first_slice_target(
    ranked: list[dict[str, Any]], preferred_targets: list[Any], *, architecture_contract_only: bool = False
) -> list[dict[str, Any]]:
    preferred = [normalize_source_ref(str(item)) for item in preferred_targets if item]
    if not ranked or not preferred:
        return ranked
    by_source = {str(item.get("source") or ""): item for item in ranked}
    best_score = int(ranked[0].get("score") or 0)
    for target in preferred:
        if target not in by_source:
            continue
        structural = infer_source_contract(dict(by_source[target].get("evidence") or by_source[target]))
        if architecture_contract_only and not architecture_contract_has_priority(target, structural):
            continue
        if not first_slice_target_can_override(by_source[target], best_score=best_score):
            continue
        selected = dict(by_source[target])
        selected["reasons"] = [
            *list(selected.get("reasons", [])),
            "ProjectArchitectureSynthesis first-slice target takes precedence over convenience-only pure transforms",
        ]
        selected["score"] = int(selected.get("score") or 0) + 80
        return [selected, *[item for item in ranked if item is not by_source[target]]]
    return ranked


def enforce_preferred_first_slice_scope(ranked: list[dict[str, Any]], preferred_targets: list[Any]) -> list[dict[str, Any]]:
    if not ranked or not preferred_targets or not FIRST_SLICE_SCOPE_POLICY.get("enforce_candidate_within_targets", True):
        return ranked
    preferred = {normalize_source_ref(str(item)) for item in preferred_targets if item}
    scoped = [item for item in ranked if normalize_source_ref(str(item.get("source") or "")) in preferred]
    if not scoped:
        return []
    reason = str(FIRST_SLICE_SCOPE_POLICY.get("selection_reason") or "ArchitectureDecisionRecord first-slice target scope")
    enriched = []
    for item in scoped:
        row = dict(item)
        row["reasons"] = [*list(row.get("reasons", [])), reason]
        enriched.append(row)
    return enriched


def first_slice_target_can_override(item: dict[str, Any], *, best_score: int) -> bool:
    source = str(item.get("source") or "").lower()
    if str(item.get("semantic_status") or "") in {"poor", "suspicious"}:
        return False
    if domain_extraction_contract(
        str(item.get("source") or ""), dict(item.get("evidence") or item)
    ).get("contract_family"):
        return True
    if int(item.get("score") or 0) < best_score - 30:
        return False
    if ranked_item_has_weak_io(item):
        return False
    structural = infer_source_contract(dict(item.get("evidence") or item))
    if architecture_target_score(source) > 0 and complete_architecture_contract(structural):
        return True
    if int(item.get("score") or 0) >= best_score:
        return True
    side_effects = {str(effect).lower() for effect in list(item.get("side_effects", []))}
    runtime_markers = (
        "send_to_model",
        "llm",
        "model",
        "provider",
        "consensus",
        "orchestrator",
        "group_manager",
        "a2a_protocol",
        "agent",
        "pipeline",
        "docker_",
        "subprocess",
        "request",
        "http",
        "network",
        "write_files",
        "copy_template",
    )
    if any(marker in source for marker in runtime_markers):
        return True
    return bool(side_effects & {"network", "subprocess", "filesystem", "filesystem_write", "database"})


def ranked_item_has_weak_io(item: dict[str, Any]) -> bool:
    evidence = dict(item.get("evidence", {}))
    signature = dict(evidence.get("signature", {}))
    args = list(signature.get("args", []) or [])
    returns = str(signature.get("returns") or "").strip()
    has_typed_input = any(isinstance(arg, dict) and str(arg.get("annotation") or "").strip() for arg in args)
    return not has_typed_input or not returns
