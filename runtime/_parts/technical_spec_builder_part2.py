from __future__ import annotations

import ast
import builtins
import re
from typing import Any
from runtime.contract_archetype_inference import contract_archetype_for_target
from runtime.role_spec_writer_ranking import (
    candidate_level_bonus as _candidate_level_bonus,
    name_and_contract_score as _name_and_contract_score,
    operational_boundary_score as _operational_boundary_score,
)
from runtime.role_skill_common import now_iso
from runtime.spec_writer_candidate_arbiter import arbitrate_candidates
from runtime.semantic_target_profiles import contract_for_target
from runtime.source_contract_semantics import infer_source_contract
from runtime.source_target_policy import is_context_only_implementation_target, is_fallback_product_target
from runtime.target_quality import semantic_target_quality_report
from runtime.technical_spec_contract_enrichment import enrich_signature_contract
from runtime.technical_spec_policy import load_technical_spec_policy, policy_list, policy_rules
_BUILTIN_NAMES = set(dir(builtins))
TECHNICAL_SPEC_POLICY = load_technical_spec_policy()
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
    allow_fallback = not any(_implementation_source(source) for source in sources)
    for source in sources:
        if not _implementation_source(str(source)) and not (allow_fallback and is_fallback_product_target(str(source))):
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
                "decorators": context.get("decorators") or snippet.get("decorators", []),
                "callers": context.get("callers", []),
                "callees": context.get("callees", []),
                "side_effects": context.get("side_effects", []),
                "contract_side_effects": context.get("contract_side_effects", context.get("side_effects", [])),
                "claims": context.get("claims", []),
                "target_binding": context.get("target_binding") or snippet.get("target_binding"),
                "symbol_occurrences": context.get("symbol_occurrences") or snippet.get("symbol_occurrences", []),
                "structural_contract": context.get("structural_contract") or snippet.get("structural_contract", {}),
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
    return is_context_only_implementation_target(lowered)

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

def _extraction_contract(
    evidence: list[dict[str, Any]], *, preferred_targets: list[Any] | None = None, advisory_config: Any = None
) -> dict[str, Any]:
    ranked = _rank_extraction_candidates(evidence); read_only_ranked_context = []
    if FIRST_SLICE_SCOPE_POLICY.get("enforce_candidate_within_targets", True):
        pre_scope_ranked = list(ranked); ranked = _enforce_preferred_first_slice_scope(ranked, preferred_targets or [])
        read_only_ranked_context = pre_scope_ranked
    else:
        ranked = _semantic_rerank_candidates(ranked, evidence)
        ranked = _promote_preferred_first_slice_target(ranked, preferred_targets or [])
    ranked = _semantic_rerank_candidates(ranked, [dict(item.get("evidence", {})) for item in ranked])
    ranked = _append_read_only_ranked_context(ranked, read_only_ranked_context)
    ranked, candidate_advisory = arbitrate_candidates(ranked, config=advisory_config)
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
    source = str(candidate.get("source") or "")
    domain_contract = _domain_extraction_contract(source)
    structural_evidence = infer_source_contract(candidate)
    signature_input_contract = _input_contract_from_candidate(candidate)
    signature_output_contract = _output_contract_from_candidate(candidate)
    contract_side_effects = _dedupe([*list(candidate.get("contract_side_effects", candidate.get("side_effects", [])) or []), *list(structural_evidence.get("observed_side_effects") or []), *list(dict(domain_contract.get("side_effect_policy") or {}).get("declared") or [])])
    enriched_contract = enrich_signature_contract(
        target=source,
        input_contract=signature_input_contract,
        output_contract=signature_output_contract,
        side_effects=contract_side_effects,
    )
    signature_input_contract = dict(enriched_contract.get("input_contract") or signature_input_contract)
    signature_output_contract = dict(enriched_contract.get("output_contract") or signature_output_contract)
    input_contract = _reconciled_input_contract(signature_input_contract, dict(domain_contract.get("input_contract") or {}), dict(domain_contract.get("input_bindings") or {}))
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
            **_side_effect_policy(contract_side_effects),
            "requires_process_boundary": bool(contract_side_effects),
            **dict(domain_contract.get("side_effect_policy") or {}),
        },
        "evidence_source": candidate.get("source"),
        "structural_evidence": structural_evidence,
        "candidate_advisory": candidate_advisory,
    }
    supporting_sources = [
        str(item) for item in list(candidate.get("contract_slice_sources") or [])
        if item and str(item) != source
    ]
    if supporting_sources:
        contract["supporting_sources"] = supporting_sources[:7]
        contract["effect_handoff_chains"] = list(candidate.get("transitive_effect_chains") or [])[:12]
    if domain_contract.get("contract_family"):
        contract["contract_family"] = domain_contract["contract_family"]
        contract["semantic_contract"] = {
            "input_contract": dict(domain_contract.get("input_contract") or {}),
            "output_contract": dict(domain_contract.get("output_contract") or {}),
        }
        contract["validation_gates"] = domain_contract.get("validation_gates", [])
        contract["failure_modes"] = domain_contract.get("failure_modes", [])
    elif enriched_contract.get("contract_profile"):
        contract["contract_profile"] = dict(enriched_contract.get("contract_profile") or {})
    contract["semantic_quality"] = semantic_target_quality_report(
        str(contract.get("candidate") or ""),
        ranked_candidates=[str(row.get("source")) for row in contract["ranked_candidates"] if isinstance(row, dict)],
        source_evidence=[str(row.get("source")) for row in evidence if row.get("source")],
        selection_reason=str(contract.get("selection_reason") or ""),
        **{"structural_evidence": structural_evidence, "input_contract": input_contract, "output_contract": output_contract, "side_effect_contract": contract["side_effects"]},
    )
    quality = dict(contract.get("semantic_quality") or {})
    quality_reasons = " ".join(str(reason) for reason in list(quality.get("reasons", []) or [])).lower()
    weak_semantic_status = str(quality.get("status") or "") in {"poor", "suspicious"}
    runtime_boundary_needs_review = "runtime/api boundary target needs semantic review" in quality_reasons
    explicitly_too_broad = "too broad for direct implementer handoff" in quality_reasons
    if not contract.get("contract_family") and (weak_semantic_status or runtime_boundary_needs_review or explicitly_too_broad):
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
def _domain_extraction_contract(source: str) -> dict[str, Any]:
    profile_contract = contract_for_target(source)
    if profile_contract:
        return profile_contract
    return contract_archetype_for_target(source)

def _reconciled_input_contract(
    signature_contract: dict[str, str], domain_contract: dict[str, Any], bindings: dict[str, Any] | None = None
) -> dict[str, str]:
    from runtime.contract_input_reconciliation import reconcile_input_contract
    return reconcile_input_contract(signature_contract, domain_contract, bindings)
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
