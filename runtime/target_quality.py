"""Quality heuristics for selected first-slice targets."""

from __future__ import annotations
from typing import Any

from .semantic_target_profiles import semantic_score_adjustments
from .source_contract_semantics import structural_quality_adjustment
from .target_structural_families import structural_contract_family_rule
from .target_quality_structural_risks import apply_structural_risk_caps
from .target_quality_predicates import (
    GENERIC_UNPROFILED_SCORE_CAP,
    META_INFRASTRUCTURE_TOKENS,
    NON_IMPLEMENTATION_DECORATORS,
    REPRESENTATIVE_TOKENS,
    SUSPICIOUS_PATH_TOKENS,
    SUSPICIOUS_SYMBOL_TOKENS,
    UNPROFILED_STRONG_PATH_TOKENS,
    UNPROFILED_STRONG_SCORE_CAP,
    bootstrap_support_symbol as _bootstrap_support_symbol,
    contextual_archetype_adjustments as _contextual_archetype_adjustments,
    generic_unprofiled_candidate as _generic_unprofiled_candidate,
    liveness_probe_symbol as _liveness_probe_symbol,
    profiled_suspicious_allowed as _profiled_suspicious_allowed,
    proven_bounded_helper as _proven_bounded_helper,
    proven_bounded_policy as _proven_bounded_policy,
    receiver_state_accessor as _receiver_state_accessor,
    runtime_boundary_hits as _runtime_boundary_hits,
    special_boundary_adjustments as _special_boundary_adjustments,
    strong_contract_hit as _strong_contract_hit,
    structurally_nontrivial as _structurally_nontrivial,
    suspicious_hits as _suspicious_hits,
    trivial_symbol as _trivial_symbol,
)


def semantic_target_quality_report(
    target: str,
    *,
    ranked_candidates: list[str] | None = None,
    source_evidence: list[str] | None = None,
    context_evidence: list[str] | None = None,
    selection_reason: str = "",
    structural_evidence: dict[str, Any] | None = None,
    input_contract: dict[str, Any] | None = None,
    output_contract: dict[str, Any] | None = None,
    side_effect_contract: dict[str, Any] | None = None,
    recognized_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not target:
        return {"status": "blocked", "target": "", "score": 0, "reasons": ["no selected extraction candidate"]}
    ranked_candidates = ranked_candidates or []
    source_evidence = source_evidence or []
    context_evidence = context_evidence or []
    lowered = target.replace("\\", "/").lower()
    symbol = lowered.rsplit(":", 1)[-1]
    path = lowered.split(":", 1)[0]
    reason_text = selection_reason.lower()
    score = 60
    reasons = ["selected extraction candidate exists"]

    if ranked_candidates and ranked_candidates[0] == target:
        score += 8
        reasons.append("candidate is ranked first by SpecWriter")
    if target in source_evidence:
        score += 8
        reasons.append("candidate is present in source evidence")
    structural_delta, structural_reasons = structural_quality_adjustment(
        dict(structural_evidence or {}),
        input_contract=input_contract,
        output_contract=output_contract,
        side_effect_contract=side_effect_contract,
    )
    score += structural_delta
    reasons.extend(structural_reasons)
    if _proven_bounded_policy(reason_text, structural_evidence, output_contract, side_effect_contract):
        score += 4
        reasons.append("Project Analyzer proved a reproducible boolean policy contract")
    if _strong_contract_hit(lowered, symbol):
        score += 18
        reasons.append("candidate name suggests a bounded contract")
    if any(token in lowered for token in REPRESENTATIVE_TOKENS):
        score += 16
        reasons.append("representative domain target / lifecycle target")
    profile_adjustments = semantic_score_adjustments(target)
    if profile_adjustments.get("profiled_contract_family"):
        archetype_adjustments = {
            "score_delta": 0,
            "reasons": [],
            "profile_ids": [],
            "benign_runtime_boundary": False,
            "profiled_contract_family": False,
        }
    else:
        archetype_adjustments = _contextual_archetype_adjustments(target, context_evidence, structural_evidence)
    score += int(profile_adjustments["score_delta"])
    score += int(archetype_adjustments["score_delta"])
    reasons.extend(profile_adjustments["reasons"])
    reasons.extend(archetype_adjustments["reasons"])
    recognized_profile = dict(recognized_profile or {})
    profile_ids = list(profile_adjustments.get("profile_ids") or [])
    if recognized_profile.get("id"):
        profile_ids.append(str(recognized_profile["id"]))
        reasons.append(str(recognized_profile.get("reason") or "promoted AST contract profile matched"))
    archetype_ids = list(archetype_adjustments.get("profile_ids") or [])
    structural_rule = structural_contract_family_rule(structural_evidence, side_effect_contract)
    structural_profile = str(structural_rule.get("family_id") or "")
    if structural_profile:
        score += int(structural_rule.get("score_bonus") or 4)
        archetype_ids.append(structural_profile)
        reasons.append("source structure proves a bounded contract family")
    profiled_contract_family = bool(
        profile_adjustments.get("profiled_contract_family")
        or archetype_adjustments.get("profiled_contract_family")
        or structural_profile
        or recognized_profile.get("contract_family")
    )
    if "pure transform" in reason_text or "deterministic parser" in reason_text:
        score += 8
        reasons.append("ranking reason marks deterministic transform")
    special_boundary = _special_boundary_adjustments(lowered, reason_text)
    score += special_boundary["score_delta"]
    reasons.extend(special_boundary["reasons"])

    suspicious = _suspicious_hits(path, symbol)
    suspicious_allowed = _profiled_suspicious_allowed(suspicious, symbol, profiled_contract_family) or bool(structural_rule.get("benign_support_path")) or _proven_bounded_helper(
        suspicious, reason_text, structural_evidence, input_contract, output_contract, side_effect_contract
    )
    meta = [token for token in META_INFRASTRUCTURE_TOKENS if token in lowered]
    boundary = _runtime_boundary_hits(lowered, symbol)
    name_looks_trivial = _trivial_symbol(symbol)
    structurally_nontrivial = _structurally_nontrivial(structural_evidence)
    receiver_state_accessor = _receiver_state_accessor(structural_evidence)
    decorators = {str(item).lower() for item in dict(structural_evidence or {}).get("decorators", [])}
    non_implementation = sorted(decorators & NON_IMPLEMENTATION_DECORATORS)
    not_implemented_stub = bool(
        "NotImplementedError" in list(dict(structural_evidence or {}).get("raises") or [])
        and int(dict(structural_evidence or {}).get("return_paths") or 0) == 0
    )
    trivial = name_looks_trivial and not structurally_nontrivial
    bootstrap = _bootstrap_support_symbol(path, symbol)
    if suspicious and not suspicious_allowed:
        score -= min(30, 10 + len(suspicious) * 5)
        reasons.append("support/utility target: " + ", ".join(suspicious[:4]))
    if meta and not (special_boundary["allow_meta"] or profiled_contract_family):
        score -= min(45, 20 + len(meta) * 8)
        reasons.append("meta-infrastructure target, not project-domain slice: " + ", ".join(meta[:4]))
    benign_boundary = bool(
        profile_adjustments["benign_runtime_boundary"]
        or archetype_adjustments["benign_runtime_boundary"]
        or structural_rule.get("benign_runtime_boundary")
        or recognized_profile.get("benign_runtime_boundary")
    )
    if boundary and not (special_boundary["allow_runtime"] or benign_boundary):
        score -= min(35, 12 + len(boundary) * 5)
        reasons.append("runtime/API boundary target needs semantic review: " + ", ".join(boundary[:4]))
    if trivial and not profiled_contract_family:
        score -= 25
        reasons.append("trivial accessor/value helper is weak as first architectural slice")
    elif name_looks_trivial and structurally_nontrivial:
        reasons.append("complete source structure proves this is not a trivial accessor")
    if _liveness_probe_symbol(symbol):
        score -= 35
        reasons.append("health/status/ping probe is weak as first architectural slice")
    if bootstrap and not profiled_contract_family:
        score -= 45
        reasons.append("CLI/bootstrap support helper is weak as first architectural slice")
    if non_implementation or not_implemented_stub:
        score -= 45
        marker = ", ".join(non_implementation) if non_implementation else "NotImplementedError-only body"
        reasons.append("declarative interface contract has no executable implementation: " + marker)
    score, risk_reasons = apply_structural_risk_caps(
        score, symbol, structural_evidence, profiled_contract_family, side_effect_contract
    )
    reasons.extend(risk_reasons)
    if receiver_state_accessor and not profiled_contract_family:
        score = min(score, 84)
        reasons.append("zero-argument receiver state accessor is weak as first architectural slice")
    reasons.extend(profile_adjustments["penalty_reasons"])
    if _generic_unprofiled_candidate(path, symbol) and not profiled_contract_family:
        if score > GENERIC_UNPROFILED_SCORE_CAP:
            score = GENERIC_UNPROFILED_SCORE_CAP
        reasons.append("unprofiled generic library contract cannot prove strong first-slice readiness")
    if score >= 95 and not profiled_contract_family and any(token in path for token in UNPROFILED_STRONG_PATH_TOKENS):
        score = min(score, UNPROFILED_STRONG_SCORE_CAP)
        reasons.append("unprofiled candidate cannot claim strong readiness from shape alone")
    executable_parser_profile = "executable grammar" in reason_text
    if "parser_combinator_helper_boundary" in profile_ids and score > 84 and not executable_parser_profile:
        score = 84
        reasons.append("parser combinator helper remains acceptable until executable grammar behavior is proven")

    score = max(0, min(100, score))
    disqualifying_boundary = boundary and not (special_boundary["allow_runtime"] or benign_boundary)
    disqualifying_meta = meta and not (special_boundary["allow_meta"] or profiled_contract_family)
    liveness_probe = _liveness_probe_symbol(symbol)
    disqualifying_trivial = trivial and not profiled_contract_family
    disqualifying_accessor = receiver_state_accessor and not profiled_contract_family
    disqualifying_bootstrap = bootstrap and not profiled_contract_family
    disqualifying_non_implementation = bool(non_implementation or not_implemented_stub)
    effective_suspicious = [] if suspicious_allowed else suspicious
    if score >= 85 and not (effective_suspicious or disqualifying_meta or disqualifying_boundary or disqualifying_trivial or disqualifying_accessor or disqualifying_bootstrap or disqualifying_non_implementation or liveness_probe or risk_reasons):
        status = "strong"
    elif score >= 65 and not (disqualifying_meta or disqualifying_trivial or disqualifying_accessor or disqualifying_bootstrap or disqualifying_non_implementation or liveness_probe or risk_reasons):
        status = "acceptable"
    elif score >= 40:
        status = "suspicious"
    else:
        status = "poor"
    return {
        "status": status,
        "target": target,
        "score": score,
        "reasons": reasons,
        "semantic_profile_ids": profile_ids,
        "contract_archetype_ids": archetype_ids,
        "profiled_contract_family": profiled_contract_family,
        "structural_evidence": dict(structural_evidence or {}),
    }

def target_quality_report(role_quality: dict[str, Any]) -> dict[str, Any]:
    target = str(role_quality.get("selected_extraction_candidate") or "")
    if not target:
        return {
            "status": "blocked",
            "target": "",
            "score": 0,
            "reasons": ["no selected extraction candidate"],
        }
    semantic = semantic_target_quality_report(target)
    lowered = target.replace("\\", "/").lower()
    score = int(semantic["score"])
    reasons = list(semantic["reasons"])
    if role_quality.get("implementation_binding_status") == "bound_to_extraction_contract":
        score += 10
        reasons.append("implementation is bound to extraction contract")
    if role_quality.get("test_has_contract_matrix"):
        score += 10
        reasons.append("contract test matrix present")
    if role_quality.get("test_has_negative_tests_for_target"):
        score += 10
        reasons.append("negative tests cover target")
    suspicious = [token for token in SUSPICIOUS_PATH_TOKENS + SUSPICIOUS_SYMBOL_TOKENS if token in lowered]
    if suspicious:
        score -= min(45, 15 + len(suspicious) * 6)
        reasons.append("suspicious utility/support target: " + ", ".join(suspicious[:4]))
    status = "good" if score >= 85 and not suspicious else "suspicious" if score >= 50 else "poor"
    return {
        "status": status,
        "target": target,
        "score": max(0, min(100, score)),
        "reasons": reasons,
    }
