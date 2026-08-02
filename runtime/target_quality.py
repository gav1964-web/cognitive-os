"""Quality heuristics for selected first-slice targets."""

from __future__ import annotations

from typing import Any

from .semantic_target_profiles import semantic_score_adjustments
from .target_quality_policy import policy_tokens, target_quality_section


TARGET_QUALITY_POLICY = target_quality_section("target_quality")
SUSPICIOUS_PATH_TOKENS = policy_tokens(TARGET_QUALITY_POLICY, "suspicious_path_tokens")
SUSPICIOUS_SYMBOL_TOKENS = policy_tokens(TARGET_QUALITY_POLICY, "suspicious_symbol_tokens")
REPRESENTATIVE_TOKENS = policy_tokens(TARGET_QUALITY_POLICY, "representative_tokens")
STRONG_CONTRACT_TOKENS = policy_tokens(TARGET_QUALITY_POLICY, "strong_contract_tokens")
STRONG_CONTRACT_PREFIXES = policy_tokens(TARGET_QUALITY_POLICY, "strong_contract_prefixes")
STRONG_CONTRACT_SYMBOLS = policy_tokens(TARGET_QUALITY_POLICY, "strong_contract_symbols")
META_INFRASTRUCTURE_TOKENS = policy_tokens(TARGET_QUALITY_POLICY, "meta_infrastructure_tokens")
RUNTIME_BOUNDARY_TOKENS = policy_tokens(TARGET_QUALITY_POLICY, "runtime_boundary_tokens")
RUNTIME_BOUNDARY_EXACT_TOKENS = policy_tokens(TARGET_QUALITY_POLICY, "runtime_boundary_exact_tokens")
TRIVIAL_SYMBOLS = set(policy_tokens(TARGET_QUALITY_POLICY, "trivial_symbols"))
TRIVIAL_PREFIXES = policy_tokens(TARGET_QUALITY_POLICY, "trivial_prefixes")
TRIVIAL_SUFFIXES = policy_tokens(TARGET_QUALITY_POLICY, "trivial_suffixes")
TRIVIAL_SUFFIX_ALLOWED_CONTAINS_ANY = policy_tokens(TARGET_QUALITY_POLICY, "trivial_suffix_allowed_contains_any")
LIVENESS_PROBE_SYMBOLS = set(policy_tokens(TARGET_QUALITY_POLICY, "liveness_probe_symbols"))
BOOTSTRAP_SYMBOLS = set(policy_tokens(TARGET_QUALITY_POLICY, "bootstrap_symbols"))
BOOTSTRAP_ARG_PATH_TOKENS = policy_tokens(TARGET_QUALITY_POLICY, "bootstrap_arg_path_tokens")
SUSPICIOUS_PATH_PARTS = set(policy_tokens(TARGET_QUALITY_POLICY, "suspicious_path_parts"))


def semantic_target_quality_report(
    target: str,
    *,
    ranked_candidates: list[str] | None = None,
    source_evidence: list[str] | None = None,
    selection_reason: str = "",
) -> dict[str, Any]:
    if not target:
        return {"status": "blocked", "target": "", "score": 0, "reasons": ["no selected extraction candidate"]}
    ranked_candidates = ranked_candidates or []
    source_evidence = source_evidence or []
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
    if _strong_contract_hit(lowered, symbol):
        score += 18
        reasons.append("candidate name suggests a bounded contract")
    if any(token in lowered for token in REPRESENTATIVE_TOKENS):
        score += 16
        reasons.append("representative domain target / lifecycle target")
    profile_adjustments = semantic_score_adjustments(target)
    score += int(profile_adjustments["score_delta"])
    reasons.extend(profile_adjustments["reasons"])
    profiled_contract_family = bool(profile_adjustments.get("profiled_contract_family"))
    if "pure transform" in reason_text or "deterministic parser" in reason_text:
        score += 8
        reasons.append("ranking reason marks deterministic transform")
    repair_boundary = "llm hypothesis boundary" in reason_text or "repair-attempt contract" in reason_text
    if repair_boundary and "send_to_model" in lowered:
        score += 18
        reasons.append("LLM repair hypothesis boundary is a valid architectural contract target")
    ml_generation_boundary = "ml inference/submission boundary" in reason_text or "ml generation" in reason_text
    if ml_generation_boundary and "generate_response" in lowered:
        score += 18
        reasons.append("ML generation boundary is a valid architectural contract target")
    prompt_lab_boundary = "prompt_lab" in lowered and (
        "first-slice target" in reason_text or "prompt-lab" in reason_text or "run artifact" in reason_text
    )
    if prompt_lab_boundary:
        score += 18
        reasons.append("prompt-lab run/artifact boundary is a valid project-domain target")

    suspicious = _suspicious_hits(path, symbol)
    meta = [token for token in META_INFRASTRUCTURE_TOKENS if token in lowered]
    boundary = _runtime_boundary_hits(lowered, symbol)
    trivial = _trivial_symbol(symbol)
    bootstrap = _bootstrap_support_symbol(path, symbol)
    if suspicious:
        score -= min(30, 10 + len(suspicious) * 5)
        reasons.append("support/utility target: " + ", ".join(suspicious[:4]))
    if meta and not prompt_lab_boundary:
        score -= min(45, 20 + len(meta) * 8)
        reasons.append("meta-infrastructure target, not project-domain slice: " + ", ".join(meta[:4]))
    benign_boundary = bool(profile_adjustments["benign_runtime_boundary"])
    if boundary and not (repair_boundary or ml_generation_boundary or benign_boundary):
        score -= min(35, 12 + len(boundary) * 5)
        reasons.append("runtime/API boundary target needs semantic review: " + ", ".join(boundary[:4]))
    if trivial and not profiled_contract_family:
        score -= 25
        reasons.append("trivial accessor/value helper is weak as first architectural slice")
    if _liveness_probe_symbol(symbol):
        score -= 35
        reasons.append("health/status/ping probe is weak as first architectural slice")
    if bootstrap and not profiled_contract_family:
        score -= 45
        reasons.append("CLI/bootstrap support helper is weak as first architectural slice")
    reasons.extend(profile_adjustments["penalty_reasons"])

    score = max(0, min(100, score))
    disqualifying_boundary = boundary and not (repair_boundary or ml_generation_boundary or benign_boundary)
    disqualifying_meta = meta and not prompt_lab_boundary
    liveness_probe = _liveness_probe_symbol(symbol)
    disqualifying_trivial = trivial and not profiled_contract_family
    disqualifying_bootstrap = bootstrap and not profiled_contract_family
    if score >= 85 and not (suspicious or disqualifying_meta or disqualifying_boundary or disqualifying_trivial or disqualifying_bootstrap or liveness_probe):
        status = "strong"
    elif score >= 65 and not (disqualifying_meta or disqualifying_trivial or disqualifying_bootstrap or liveness_probe):
        status = "acceptable"
    elif score >= 40:
        status = "suspicious"
    else:
        status = "poor"
    return {"status": status, "target": target, "score": score, "reasons": reasons}


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


def _runtime_boundary_hits(lowered: str, symbol: str) -> list[str]:
    hits = []
    for token in RUNTIME_BOUNDARY_TOKENS:
        if token in RUNTIME_BOUNDARY_EXACT_TOKENS:
            if token == symbol or symbol.startswith(f"{token}_") or symbol.endswith(f"_{token}") or f"_{token}_" in symbol:
                hits.append(token)
            continue
        if token in lowered:
            hits.append(token)
    return hits


def _strong_contract_hit(lowered: str, symbol: str) -> bool:
    normalized_symbol = symbol.lstrip("_")
    if normalized_symbol in STRONG_CONTRACT_SYMBOLS:
        return True
    if normalized_symbol.startswith(STRONG_CONTRACT_PREFIXES):
        return True
    return any(token in lowered for token in STRONG_CONTRACT_TOKENS)


def _trivial_symbol(symbol: str) -> bool:
    if symbol in TRIVIAL_SYMBOLS:
        return True
    if symbol.startswith(TRIVIAL_PREFIXES):
        return True
    if symbol.endswith(TRIVIAL_SUFFIXES) and not any(token in symbol for token in TRIVIAL_SUFFIX_ALLOWED_CONTAINS_ANY):
        return True
    return False


def _liveness_probe_symbol(symbol: str) -> bool:
    return symbol in LIVENESS_PROBE_SYMBOLS


def _bootstrap_support_symbol(path: str, symbol: str) -> bool:
    if symbol in BOOTSTRAP_SYMBOLS:
        return True
    if symbol.endswith("_args") and any(token in path for token in BOOTSTRAP_ARG_PATH_TOKENS):
        return True
    return False


def _suspicious_hits(path: str, symbol: str) -> list[str]:
    hits = [token for token in SUSPICIOUS_PATH_TOKENS if token in path]
    hits.extend(token for token in SUSPICIOUS_SYMBOL_TOKENS if token in symbol)
    path_parts = {part for part in path.replace("\\", "/").split("/") if part}
    if path_parts.intersection(SUSPICIOUS_PATH_PARTS) and "icon" not in hits:
        hits.append("icon")
    return hits
