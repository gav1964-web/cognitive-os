from __future__ import annotations

import ast
import builtins
import re
from typing import Any
from runtime.role_spec_writer_ranking import (
    candidate_level_bonus as _candidate_level_bonus,
    name_and_contract_score as _name_and_contract_score,
    operational_boundary_score as _operational_boundary_score,
)
from runtime.role_skill_common import now_iso
from runtime.semantic_target_profiles import contract_for_target
from runtime.target_quality import semantic_target_quality_report
from runtime.technical_spec_policy import load_technical_spec_policy, policy_list, policy_rules

_BUILTIN_NAMES = set(dir(builtins))
TECHNICAL_SPEC_POLICY = load_technical_spec_policy()
CONTEXT_ONLY_SOURCE_PATH_TOKENS = policy_list(TECHNICAL_SPEC_POLICY, "context_only_source_path_tokens")
SNIPPET_POLICY = dict(TECHNICAL_SPEC_POLICY["snippet_analysis"])
CONTRACT_TYPE_POLICY = dict(TECHNICAL_SPEC_POLICY["contract_type_inference"])
SEMANTIC_RERANK_POLICY = dict(TECHNICAL_SPEC_POLICY["semantic_rerank"])
FIRST_SLICE_SCOPE_POLICY = dict(TECHNICAL_SPEC_POLICY.get("first_slice_scope") or {})
ARCHITECTURE_SHAPE_POLICY = dict(TECHNICAL_SPEC_POLICY["architecture_shape_score"])
SIDE_EFFECT_PROCESS_BOUNDARY = set(policy_list(TECHNICAL_SPEC_POLICY, "side_effect_process_boundary"))
ALLOWED_EXTERNAL_SNIPPET_NAMES = {str(item) for item in SNIPPET_POLICY.get("allowed_external_names", [])}
HIGH_CONFIDENCE_UNRESOLVED_SETS = tuple(
    frozenset(str(item) for item in row)
    for row in SNIPPET_POLICY.get("high_confidence_unresolved_sets", [])
    if isinstance(row, list)
)
IGNORED_RETURN_ANNOTATIONS = set(policy_list(CONTRACT_TYPE_POLICY, "ignored_return_annotations"))
ARGUMENT_TYPE_RULES = policy_rules(CONTRACT_TYPE_POLICY, "argument_rules")
PAYLOAD_TYPE_RULES = policy_rules(CONTRACT_TYPE_POLICY, "payload_rules")
RESULT_TYPE_RULES = policy_rules(CONTRACT_TYPE_POLICY, "result_rules")

def _fallback_work_plan_contract(targets: list[str]) -> dict[str, Any]:
    targets = _dedupe([_normalize_source_ref(str(item)) for item in targets if item])
    primary = targets[0]
    steps = [
        f"Define explicit input/output contract for {primary}.",
        f"Record side-effect and retry policy for {primary}.",
        f"Attach source-linked acceptance and negative-test expectations for {primary}.",
    ]
    return {
        "status": "ready",
        "source": "TechnicalSpec.fallback_from_spec_writer_brief",
        "name": "extraction_contract_slice",
        "goal": f"Prepare a bounded implementation handoff for `{primary}` from source-backed SpecWriter evidence.",
        "targets": targets[:24],
        "knowledge_rule": None,
        "obligations": [
            {
                "id": f"WPC-{index:03d}",
                "step": step,
                "target": primary,
                "input": "source-backed evidence, current behavior, and declared capability boundary",
                "output": "bounded implementation obligation with acceptance and rollback evidence",
                "verification": "must be linked to at least one acceptance criterion before Implementer handoff",
            }
            for index, step in enumerate(steps, start=1)
        ],
    }

def _human_review_material(
    architecture_decision: dict[str, Any],
    extraction_contract: dict[str, Any],
    quality_gate: dict[str, Any],
) -> dict[str, Any]:
    candidate = str(extraction_contract.get("candidate") or "no candidate selected")
    open_questions = list(architecture_decision.get("open_questions") or [])
    non_goals = list(architecture_decision.get("non_goals") or [])
    return {
        "open_questions": open_questions,
        "non_goals": non_goals,
        "decision_points": [
            {
                "topic": "first_slice_scope",
                "decision": f"Confirm that `{candidate}` is the intended first bounded implementation target.",
                "evidence": extraction_contract.get("source") or candidate,
            },
            {
                "topic": "quality_gate",
                "decision": "Accept, block, or request rework based on the engineering quality gate.",
                "evidence": quality_gate.get("status"),
            },
        ],
        "release_note": "This TechnicalSpec is an API artifact between SpecWriter and Implementer; it is not permission to edit source code.",
    }

def _source_evidence(brief: dict[str, Any], source_context: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    first_slice = dict(brief.get("first_slice") or {})
    contract_targets = [
        target.get("source")
        for target in list(brief.get("contract_targets", []) or [])
        if isinstance(target, dict) and target.get("source")
    ]
    sources = _dedupe(
        [
            *[_normalize_source_ref(str(source)) for source in list(brief.get("files_or_symbols", []) or []) if source],
            *[_normalize_source_ref(str(source)) for source in list(first_slice.get("targets", []) or []) if source],
            *[_normalize_source_ref(str(source)) for source in contract_targets if source],
        ]
    )
    for source in sources:
        if not _implementation_source(str(source)):
            continue
        source = _normalize_source_ref(str(source))
        context = dict(source_context.get(str(source), {}))
        snippet_value = context.get("snippet", {})
        snippet = dict(snippet_value) if isinstance(snippet_value, dict) else {"text": str(snippet_value or "")}
        signature = dict(context.get("signature", {}))
        rows.append(
            {
                "source": str(source),
                "kind": context.get("kind") or "unknown",
                "snippet": snippet.get("text"),
                "signature": signature,
                "callers": context.get("callers", []),
                "callees": context.get("callees", []),
                "side_effects": context.get("side_effects", []),
                "claims": context.get("claims", []),
                "target_binding": context.get("target_binding") or snippet.get("target_binding"),
                "symbol_occurrences": context.get("symbol_occurrences") or snippet.get("symbol_occurrences", []),
            }
        )
    return rows

def _implementation_source(source: str) -> bool:
    lowered = source.lower()
    if _context_only_implementation_source(lowered):
        return False
    if ".py:" in lowered:
        return True
    if lowered.endswith(".py"):
        return True
    if lowered.startswith("[") and " " in lowered:
        return True
    return False

def _context_only_implementation_source(lowered: str) -> bool:
    normalized = "/" + lowered.replace("\\", "/").lstrip("/")
    return any(token in normalized for token in CONTEXT_ONLY_SOURCE_PATH_TOKENS)

def _normalize_source_ref(source: str) -> str:
    return re.sub(r"\s*\(\d+\s+loc\)\s*$", "", str(source or "").strip(), flags=re.IGNORECASE)

def _dedupe(values: list[str]) -> list[str]:
    seen = set()
    rows = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        rows.append(value)
    return rows

def _extraction_contract(evidence: list[dict[str, Any]], *, preferred_targets: list[Any] | None = None) -> dict[str, Any]:
    ranked = _rank_extraction_candidates(evidence)
    if FIRST_SLICE_SCOPE_POLICY.get("enforce_candidate_within_targets", True):
        ranked = _enforce_preferred_first_slice_scope(ranked, preferred_targets or [])
    else:
        ranked = _semantic_rerank_candidates(ranked, evidence)
        ranked = _promote_preferred_first_slice_target(ranked, preferred_targets or [])
    ranked = _semantic_rerank_candidates(ranked, [dict(item.get("evidence", {})) for item in ranked])
    if not ranked:
        return {
            "status": "blocked_no_safe_candidate",
            "candidate": None,
            "candidate_score": 0,
            "selection_reason": "no source-specific evidence available for a bounded extraction contract",
            "ranked_candidates": [],
            "semantic_quality": semantic_target_quality_report(""),
            "input_contract": {},
            "output_contract": {},
            "side_effects": {"declared": [], "requires_process_boundary": False},
            "evidence_source": None,
            "blocked_by": ["no_safe_source_specific_candidate"],
        }
    candidate = dict(ranked[0].get("evidence", {})) if ranked else {}
    args = list(dict(candidate.get("signature", {})).get("args", []))
    source = str(candidate.get("source") or "")
    domain_contract = _domain_extraction_contract(source)
    signature_input_contract = _input_contract_from_candidate(candidate)
    signature_output_contract = _output_contract_from_candidate(candidate)
    input_contract = _reconciled_input_contract(signature_input_contract, dict(domain_contract.get("input_contract") or {}))
    output_contract = dict(domain_contract.get("output_contract") or signature_output_contract)
    contract = {
        "candidate": candidate.get("source"),
        "candidate_score": ranked[0]["score"] if ranked else 0,
        "selection_reason": "; ".join(ranked[0]["reasons"]) if ranked else "no source evidence available",
        "ranked_candidates": [
            {
                "source": item.get("source"),
                "kind": item.get("kind"),
                "score": item.get("score"),
                "reasons": item.get("reasons", []),
                "side_effects": item.get("side_effects", []),
            }
            for item in ranked[:32]
        ],
        "input_contract": input_contract,
        "output_contract": output_contract,
        "side_effects": {
            "declared": candidate.get("side_effects", []),
            "requires_process_boundary": bool(candidate.get("side_effects")),
            **dict(domain_contract.get("side_effect_policy") or {}),
        },
        "evidence_source": candidate.get("source"),
    }
    if domain_contract.get("contract_family"):
        contract["contract_family"] = domain_contract["contract_family"]
        contract["semantic_contract"] = {
            "input_contract": dict(domain_contract.get("input_contract") or {}),
            "output_contract": dict(domain_contract.get("output_contract") or {}),
        }
        contract["validation_gates"] = domain_contract.get("validation_gates", [])
        contract["failure_modes"] = domain_contract.get("failure_modes", [])
    contract["semantic_quality"] = semantic_target_quality_report(
        str(contract.get("candidate") or ""),
        ranked_candidates=[str(row.get("source")) for row in contract["ranked_candidates"] if isinstance(row, dict)],
        source_evidence=[str(row.get("source")) for row in evidence if row.get("source")],
        selection_reason=str(contract.get("selection_reason") or ""),
    )
    quality = dict(contract.get("semantic_quality") or {})
    quality_reasons = " ".join(str(reason) for reason in list(quality.get("reasons", []) or [])).lower()
    weak_semantic_status = str(quality.get("status") or "") in {"poor", "suspicious"}
    runtime_boundary_needs_review = "runtime/api boundary target needs semantic review" in quality_reasons
    if not contract.get("contract_family") and (weak_semantic_status or runtime_boundary_needs_review):
        review = _semantic_review_override(contract, quality, preferred_targets or [])
        if review.get("status") == "approved_with_constraints":
            contract["semantic_review"] = review
            return contract
        return {
            "status": "blocked_no_safe_candidate",
            "candidate": None,
            "candidate_score": 0,
            "selection_reason": (
                "best available source candidate requires semantic review before implementer handoff; "
                "scope clarification or L4.5 semantic review is required before implementer handoff"
            ),
            "ranked_candidates": contract["ranked_candidates"],
            "semantic_quality": quality,
            "input_contract": {},
            "output_contract": {},
            "side_effects": {"declared": [], "requires_process_boundary": False},
            "evidence_source": None,
            "blocked_by": [
                "no_safe_source_specific_candidate",
                "selected_candidate_semantic_quality_requires_review",
            ],
        }
    return contract

def _semantic_review_override(contract: dict[str, Any], quality: dict[str, Any], preferred_targets: list[Any]) -> dict[str, Any]:
    policy = dict(TECHNICAL_SPEC_POLICY.get("semantic_review_override") or {})
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
        "candidate_score_high_enough": int(contract.get("candidate_score") or 0) >= int(policy.get("min_candidate_score") or 0),
        "candidate_in_first_slice": not policy.get("required_candidate_in_first_slice", True) or candidate in preferred,
        "source_evidence_bound": bool(contract.get("evidence_source") == candidate),
        "io_contract_bound": bool(contract.get("input_contract") and contract.get("output_contract")),
        "no_side_effects": not bool(dict(contract.get("side_effects") or {}).get("declared")),
        "required_reason_tokens_present": all(token in reason_text for token in required),
    }

def _domain_extraction_contract(source: str) -> dict[str, Any]:
    profile_contract = contract_for_target(source)
    if profile_contract:
        return profile_contract
    return {}

def _reconciled_input_contract(signature_contract: dict[str, str], domain_contract: dict[str, Any]) -> dict[str, str]:
    if not signature_contract:
        return {str(key): str(value) for key, value in domain_contract.items()}
    if not domain_contract:
        return signature_contract
    signature_keys = list(signature_contract)
    domain_keys = list(domain_contract)
    if signature_keys == domain_keys:
        return {key: str(domain_contract.get(key) or signature_contract[key]) for key in signature_keys}
    if len(signature_keys) == len(domain_keys):
        return {
            signature_key: str(domain_contract.get(domain_key) or signature_contract[signature_key])
            for signature_key, domain_key in zip(signature_keys, domain_keys)
        }
    aggregate_keys = {"consensus_input", "failure_evidence"}
    if aggregate_keys & set(str(key) for key in domain_contract):
        return {str(key): str(value) for key, value in domain_contract.items()}
    return signature_contract

def _promote_preferred_first_slice_target(ranked: list[dict[str, Any]], preferred_targets: list[Any]) -> list[dict[str, Any]]:
    preferred = [_normalize_source_ref(str(item)) for item in preferred_targets if item]
    if not ranked or not preferred:
        return ranked
    by_source = {str(item.get("source") or ""): item for item in ranked}
    best_score = int(ranked[0].get("score") or 0)
    for target in preferred:
        if target not in by_source:
            continue
        if not _first_slice_target_can_override(by_source[target], best_score=best_score):
            continue
        selected = dict(by_source[target])
        selected["reasons"] = [
            *list(selected.get("reasons", [])),
            "ProjectArchitectureSynthesis first-slice target takes precedence over convenience-only pure transforms",
        ]
        selected["score"] = int(selected.get("score") or 0) + 80
        return [selected, *[item for item in ranked if item is not by_source[target]]]
    return ranked

def _enforce_preferred_first_slice_scope(ranked: list[dict[str, Any]], preferred_targets: list[Any]) -> list[dict[str, Any]]:
    if not ranked or not preferred_targets or not FIRST_SLICE_SCOPE_POLICY.get("enforce_candidate_within_targets", True):
        return ranked
    preferred = {_normalize_source_ref(str(item)) for item in preferred_targets if item}
    scoped = [item for item in ranked if _normalize_source_ref(str(item.get("source") or "")) in preferred]
    if not scoped:
        return []
    reason = str(FIRST_SLICE_SCOPE_POLICY.get("selection_reason") or "ArchitectureDecisionRecord first-slice target scope")
    enriched = []
    for item in scoped:
        row = dict(item)
        row["reasons"] = [*list(row.get("reasons", [])), reason]
        enriched.append(row)
    return enriched

def _first_slice_target_can_override(item: dict[str, Any], *, best_score: int) -> bool:
    source = str(item.get("source") or "").lower()
    if _domain_extraction_contract(str(item.get("source") or "")).get("contract_family"):
        return True
    if int(item.get("score") or 0) < best_score - 30:
        return False
    if _ranked_item_has_weak_io(item):
        return False
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

def _ranked_item_has_weak_io(item: dict[str, Any]) -> bool:
    evidence = dict(item.get("evidence", {}))
    signature = dict(evidence.get("signature", {}))
    args = list(signature.get("args", []) or [])
    returns = str(signature.get("returns") or "").strip()
    has_typed_input = any(isinstance(arg, dict) and str(arg.get("annotation") or "").strip() for arg in args)
    return not has_typed_input or not returns
