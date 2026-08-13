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
from runtime.source_contract_semantics import infer_source_contract
from runtime.target_quality import semantic_target_quality_report
from runtime.technical_spec_policy import load_technical_spec_policy, policy_list, policy_rules
from runtime._parts.technical_spec_builder_part3 import (
    _input_contract_from_candidate,
    _output_contract_from_candidate,
)

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

def _step_target(first_slice: dict[str, Any], index: int) -> str | None:
    targets = [str(item) for item in list(first_slice.get("targets", [])) if item]
    if not targets:
        return None
    return targets[min(index - 1, len(targets) - 1)]

def _stage_contract_expectation(stage: str) -> str:
    lowered = stage.lower()
    if "input" in lowered:
        return "input must be validated and recorded before transformation"
    if "output" in lowered:
        return "output must match declared schema or artifact path policy"
    return "intermediate shape must be named before handoff"

def _hint_text(value: object, default: str) -> str:
    if isinstance(value, list) and value:
        return str(value[0])
    text = str(value or "").strip()
    return text or default

def _rank_extraction_candidates(evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ranked = []
    for index, row in enumerate(evidence):
        candidate = dict(row)
        score = 0
        reasons = []
        kind = str(candidate.get("kind") or "")
        side_effects = list(candidate.get("side_effects", []) or [])
        signature = dict(candidate.get("signature", {}) or {})
        claims = [str(item) for item in candidate.get("claims", []) or []]
        decorators = {str(item).lower().rsplit(".", 1)[-1] for item in candidate.get("decorators", []) or []}

        if kind == "pure_transform":
            score += 40
            reasons.append("pure transform candidate")
        elif kind == "bounded_policy":
            score += 55
            reasons.append("bounded reproducible policy decision")
        elif kind == "central_flow_node":
            score += 45
            reasons.append("central flow node with subsystem-level evidence")
        elif kind == "broad_function":
            score += 38
            reasons.append("broad function can anchor a meaningful first slice")
        else:
            score += 5
            reasons.append("available source evidence")

        if candidate.get("central_flow_node"):
            score += 20
            reasons.append("central flow evidence available")
        if candidate.get("mixed_responsibilities"):
            score += 12
            reasons.append("mixed-responsibility evidence available")
        if candidate.get("process_boundary_reasons"):
            score += 8
            reasons.append("process-boundary evidence available")
        if candidate.get("candidate_level"):
            score += _candidate_level_bonus(str(candidate.get("candidate_level")))
            reasons.append(f"ProjectMapReport ranked as {candidate.get('candidate_level')}")
        if candidate.get("candidate_score") is not None:
            score += min(int(candidate.get("candidate_score") or 0), 100) // 20
            reasons.append("ProjectMapReport candidate score available")
        if "property" in decorators:
            score -= 90
            reasons.append("property accessor is state evidence, not a meaningful first slice")

        if not side_effects:
            score += 25
            reasons.append("no declared side effects")
        else:
            score -= 20
            reasons.append("declared side effects require tighter isolation")

        if signature.get("args"):
            score += 10
            reasons.append("input contract can be inferred from signature")
        if signature.get("returns"):
            score += 10
            reasons.append("output contract can be inferred from signature")
        if candidate.get("snippet"):
            score += 5
            reasons.append("snippet available for source-backed review")
        if _pass_only_snippet(candidate.get("snippet")):
            score -= 120
            reasons.append("pass-only callable has no implementation contract")
        unresolved_names = _high_confidence_unresolved_snippet_names(candidate)
        if unresolved_names:
            score -= 70
            reasons.append("snippet references unresolved names: " + ", ".join(unresolved_names[:6]))
        if candidate.get("target_binding") == "ambiguous_method_symbol":
            score -= 48
            reasons.append("method symbol is ambiguous across classes and needs class-qualified target binding")
        if candidate.get("callers"):
            score += 5
            reasons.append("caller context available")
        name_score, name_reasons = _name_and_contract_score(str(candidate.get("source") or ""), signature, side_effects)
        score += name_score
        reasons.extend(name_reasons)
        if any("idempotency" in claim.lower() for claim in claims):
            score -= 10
            reasons.append("idempotency risk claim present")
        if any("side effect" in claim.lower() for claim in claims):
            score -= 10
            reasons.append("side-effect risk claim present")
        policy_score, policy_reasons = _operational_boundary_score(str(candidate.get("source") or ""), signature, claims)
        score += policy_score
        reasons.extend(policy_reasons)
        shape_score, shape_reasons = _architecture_shape_score(str(candidate.get("source") or ""))
        score += shape_score
        reasons.extend(shape_reasons)

        ranked.append(
            {
                "source": candidate.get("source"),
                "kind": candidate.get("kind"),
                "score": score,
                "reasons": reasons,
                "side_effects": side_effects,
                "target_binding": candidate.get("target_binding"),
                "evidence": candidate,
                "index": index,
            }
        )
    return sorted(ranked, key=lambda item: (-int(item["score"]), int(item["index"]), str(item.get("source") or "")))


def _pass_only_snippet(value: object) -> bool:
    snippet = _snippet_text(value)
    if not snippet or "..." in snippet:
        return False
    try:
        tree = ast.parse(snippet)
    except SyntaxError:
        return False
    function = next((node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))), None)
    if function is None:
        return False
    body = [node for node in function.body if not (isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str))]
    return len(body) == 1 and isinstance(body[0], ast.Pass)

def _high_confidence_unresolved_snippet_names(candidate: dict[str, Any]) -> list[str]:
    snippet = _snippet_text(candidate.get("snippet"))
    if not snippet or "..." in snippet:
        return []
    try:
        tree = ast.parse(snippet)
    except SyntaxError:
        return []
    local_names = set(_signature_arg_names(candidate))
    loaded_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            if isinstance(node.ctx, ast.Load):
                loaded_names.add(node.id)
            elif isinstance(node.ctx, (ast.Store, ast.Del)):
                local_names.add(node.id)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            local_names.add(node.name)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                local_names.update(arg.arg for arg in node.args.args)
                local_names.update(arg.arg for arg in node.args.kwonlyargs)
                if node.args.vararg:
                    local_names.add(node.args.vararg.arg)
                if node.args.kwarg:
                    local_names.add(node.args.kwarg.arg)
        elif isinstance(node, ast.Import):
            local_names.update(alias.asname or alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            local_names.update(alias.asname or alias.name for alias in node.names)
    unresolved = sorted(
        name
        for name in loaded_names
        if name not in local_names and name not in _BUILTIN_NAMES and name not in ALLOWED_EXTERNAL_SNIPPET_NAMES
    )
    unresolved_set = set(unresolved)
    for required_set in HIGH_CONFIDENCE_UNRESOLVED_SETS:
        if required_set.issubset(unresolved_set):
            return [name for name in unresolved if name in required_set]
    return []

def _snippet_text(value: object) -> str:
    if isinstance(value, dict):
        return str(value.get("text") or "")
    return str(value or "")

def _signature_arg_names(candidate: dict[str, Any]) -> list[str]:
    signature = dict(candidate.get("signature", {}) or {})
    names = []
    for row in signature.get("args", []) or []:
        if isinstance(row, dict) and row.get("name"):
            names.append(str(row["name"]))
    return names

def _semantic_rerank_candidates(ranked: list[dict[str, Any]], evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if len(ranked) < 2:
        return ranked
    evidence_sources = [str(row.get("source")) for row in evidence if row.get("source")]
    ranked_sources = [str(row.get("source")) for row in ranked if row.get("source")]
    enriched = []
    for item in ranked:
        candidate = dict(item)
        candidate_evidence = dict(candidate.get("evidence") or {})
        target = str(candidate.get("source") or "")
        hypothetical_ranking = [target, *[source for source in ranked_sources if source != target]]
        side_effects = list(
            candidate_evidence.get("contract_side_effects", candidate_evidence.get("side_effects", [])) or []
        )
        quality = semantic_target_quality_report(
            target,
            ranked_candidates=hypothetical_ranking,
            source_evidence=evidence_sources,
            selection_reason="; ".join(str(reason) for reason in candidate.get("reasons", [])),
            structural_evidence=infer_source_contract(candidate_evidence),
            input_contract=_input_contract_from_candidate(candidate_evidence),
            output_contract=_output_contract_from_candidate(candidate_evidence),
            side_effect_contract={"declared": side_effects, "requires_process_boundary": bool(side_effects)},
        )
        candidate["semantic_quality"] = quality
        candidate["semantic_score"] = int(quality.get("score") or 0)
        candidate["semantic_status"] = str(quality.get("status") or "")
        enriched.append(candidate)
    first = enriched[0]
    replacement = _best_semantic_replacement(enriched)
    if replacement is None or replacement is first:
        return enriched
    replacement["reasons"] = [
        *list(replacement.get("reasons", [])),
        "semantic rerank selected a stronger bounded first-slice target",
    ]
    return [replacement, *[item for item in enriched if item is not replacement]]

def _best_semantic_replacement(ranked: list[dict[str, Any]]) -> dict[str, Any] | None:
    first = ranked[0]
    first_semantic = int(first.get("semantic_score") or 0)
    first_score = int(first.get("score") or 0)
    scan_limit = int(SEMANTIC_RERANK_POLICY.get("scan_limit") or 12)
    candidates = [
        item
        for item in ranked[1:scan_limit]
        if _semantic_candidate_is_better(item, first=first, first_semantic=first_semantic, first_score=first_score)
    ]
    if not candidates:
        return None
    return sorted(
        candidates,
        key=lambda item: (
            0 if item.get("semantic_status") == "strong" else 1,
            -int(item.get("semantic_score") or 0),
            -int(item.get("score") or 0),
            int(item.get("index") or 0),
        ),
    )[0]

def _semantic_candidate_is_better(item: dict[str, Any], *, first: dict[str, Any], first_semantic: int, first_score: int) -> bool:
    status = str(item.get("semantic_status") or "")
    semantic_score = int(item.get("semantic_score") or 0)
    score = int(item.get("score") or 0)
    if _would_replace_executable_ready_target_with_method(first, item, first_score=first_score, score=score):
        return False
    reason_text = " ".join(str(reason) for reason in item.get("reasons", [])).lower()
    first_reason_text = " ".join(str(reason) for reason in first.get("reasons", [])).lower()
    if "framework request/response boundary, not first reusable core contract" in reason_text and score < first_score:
        return False
    bounded_transform = "deterministic parser/normalizer/validator shape" in reason_text
    first_is_bounded_transform = "deterministic parser/normalizer/validator shape" in first_reason_text
    if (
        status == "strong"
        and bounded_transform
        and not first_is_bounded_transform
        and semantic_score >= first_semantic
        and score >= first_score - int(SEMANTIC_RERANK_POLICY.get("bounded_transform_score_slack") or 55)
    ):
        return True
    if status == "strong" and semantic_score >= first_semantic + int(SEMANTIC_RERANK_POLICY.get("strong_semantic_delta") or 8) and score >= first_score - int(SEMANTIC_RERANK_POLICY.get("strong_score_slack") or 35):
        return True
    if status == "strong" and semantic_score >= first_semantic + int(SEMANTIC_RERANK_POLICY.get("strong_close_semantic_delta") or 6) and score >= first_score - int(SEMANTIC_RERANK_POLICY.get("strong_close_score_slack") or 10):
        return True
    if semantic_score >= first_semantic + int(SEMANTIC_RERANK_POLICY.get("generic_semantic_delta") or 18) and score >= first_score - int(SEMANTIC_RERANK_POLICY.get("generic_score_slack") or 20):
        return True
    return False

def _would_replace_executable_ready_target_with_method(
    first: dict[str, Any], item: dict[str, Any], *, first_score: int, score: int
) -> bool:
    reasons = " ".join(str(reason) for reason in list(first.get("reasons", []) or [])).lower()
    return (
        (str(item.get("kind") or "") == "method" or str(item.get("target_binding") or "") == "method_symbol")
        and "inputs look materializable by executable acceptance fixtures" in reasons
        and first_score >= score + 10
    )

def _architecture_shape_score(source: str) -> tuple[int, list[str]]:
    lowered = source.lower()
    score = 0
    reasons: list[str] = []
    if any(token in lowered for token in policy_list(ARCHITECTURE_SHAPE_POLICY, "positive_source_tokens")):
        score += int(ARCHITECTURE_SHAPE_POLICY.get("positive_source_bonus") or 0)
        reasons.append(str(ARCHITECTURE_SHAPE_POLICY.get("positive_source_reason") or "architecture-useful source boundary"))
    if any(token in lowered for token in policy_list(ARCHITECTURE_SHAPE_POLICY, "positive_symbol_tokens")):
        score += int(ARCHITECTURE_SHAPE_POLICY.get("positive_symbol_bonus") or 0)
        reasons.append(str(ARCHITECTURE_SHAPE_POLICY.get("positive_symbol_reason") or "domain boundary function name"))
    if any(token in lowered for token in policy_list(ARCHITECTURE_SHAPE_POLICY, "negative_source_tokens")):
        score -= int(ARCHITECTURE_SHAPE_POLICY.get("negative_source_penalty") or 0)
        reasons.append(str(ARCHITECTURE_SHAPE_POLICY.get("negative_source_reason") or "generic helper is lower priority"))
    if any(token in lowered for token in policy_list(ARCHITECTURE_SHAPE_POLICY, "background_worker_tokens")):
        score -= int(ARCHITECTURE_SHAPE_POLICY.get("background_worker_penalty") or 0)
        reasons.append(str(ARCHITECTURE_SHAPE_POLICY.get("background_worker_reason") or "background worker is evidence"))
    return score, reasons

def _requirement_statement(requirement: str, source: object) -> str:
    source_text = str(source or "").strip()
    if requirement == "Capability candidate requires TechnicalSpec." and source_text:
        return f"{source_text} must have explicit input/output contract, side-effect policy, and Foundry quality gate."
    if requirement == "Risk must be addressed or accepted before promotion." and source_text:
        return f"Risk from {source_text} must be mitigated or explicitly accepted before promotion."
    return requirement

def _acceptance_targets(brief: dict[str, Any], traceability: list[dict[str, Any]]) -> list[dict[str, str]]:
    rows = []
    for row in traceability[:40]:
        source = row.get("source")
        requirement = str(row.get("acceptance") or row.get("requirement") or "")
        rows.append({"source": str(source or ""), "criterion": _acceptance_statement(requirement, source)})
    seen_sources = {row["source"] for row in rows if row.get("source")}
    for source in brief.get("files_or_symbols", []) or []:
        source_text = str(source or "")
        if not source_text or source_text in seen_sources:
            continue
        rows.append({"source": source_text, "criterion": _acceptance_statement("Capability candidate requires TechnicalSpec.", source_text)})
        seen_sources.add(source_text)
    if rows:
        return rows
    return [
        {"source": "spec_writer_brief", "criterion": str(item)}
        for item in brief.get("acceptance_targets", [])
        if item
    ]

def _acceptance_statement(requirement: str, source: object) -> str:
    source_text = str(source or "").strip()
    if requirement == "Capability candidate requires TechnicalSpec." and source_text:
        return f"{source_text} has a bounded TechnicalSpec with source evidence, input contract, output contract, and negative-test expectation."
    if requirement == "Risk must be addressed or accepted before promotion." and source_text:
        return f"{source_text} risk is represented in constraints, acceptance criteria, or non-goals before any implementation handoff."
    return requirement or f"{source_text} is covered by the TechnicalSpec."
