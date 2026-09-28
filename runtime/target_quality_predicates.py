"""Policy predicates used by target quality scoring."""

from __future__ import annotations

from typing import Any

from .contract_archetype_inference import archetype_score_adjustments
from .source_contract_types import all_contract_shapes_concrete
from .target_quality_context import owner_qualified_target
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
GENERIC_UNPROFILED_SYMBOLS = set(policy_tokens(TARGET_QUALITY_POLICY, "generic_unprofiled_symbols"))
GENERIC_UNPROFILED_SYMBOL_CONTAINS_ANY = policy_tokens(TARGET_QUALITY_POLICY, "generic_unprofiled_symbol_contains_any")
GENERIC_UNPROFILED_PATH_TOKENS = policy_tokens(TARGET_QUALITY_POLICY, "generic_unprofiled_path_tokens")
GENERIC_UNPROFILED_SCORE_CAP = int(policy_tokens(TARGET_QUALITY_POLICY, "generic_unprofiled_score_cap")[0])
UNPROFILED_STRONG_SCORE_CAP = int(policy_tokens(TARGET_QUALITY_POLICY, "unprofiled_strong_score_cap")[0])
UNPROFILED_STRONG_PATH_TOKENS = policy_tokens(TARGET_QUALITY_POLICY, "unprofiled_strong_path_tokens")
NON_IMPLEMENTATION_DECORATORS = set(policy_tokens(TARGET_QUALITY_POLICY, "non_implementation_decorators"))


def contextual_archetype_adjustments(
    target: str,
    context_evidence: list[str],
    structural_evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    direct = archetype_score_adjustments(owner_qualified_target(target, structural_evidence))
    if direct.get("profile_ids"):
        return direct
    for context in context_evidence:
        contextual = archetype_score_adjustments(f"{context}/{target}")
        if contextual.get("profile_ids"):
            return contextual
    return direct


def runtime_boundary_hits(lowered: str, symbol: str) -> list[str]:
    hits = []
    for token in RUNTIME_BOUNDARY_TOKENS:
        if token in RUNTIME_BOUNDARY_EXACT_TOKENS:
            if token == symbol or symbol.startswith(f"{token}_") or symbol.endswith(f"_{token}") or f"_{token}_" in symbol:
                hits.append(token)
            continue
        if token in lowered:
            hits.append(token)
    return hits


def strong_contract_hit(lowered: str, symbol: str) -> bool:
    normalized_symbol = symbol.lstrip("_")
    if normalized_symbol in STRONG_CONTRACT_SYMBOLS:
        return True
    if normalized_symbol.startswith(STRONG_CONTRACT_PREFIXES):
        return True
    return any(token in lowered for token in STRONG_CONTRACT_TOKENS)


def trivial_symbol(symbol: str) -> bool:
    if symbol in TRIVIAL_SYMBOLS:
        return True
    if symbol.startswith(TRIVIAL_PREFIXES) and not any(token in symbol for token in TRIVIAL_SUFFIX_ALLOWED_CONTAINS_ANY):
        return True
    if symbol.endswith(TRIVIAL_SUFFIXES) and not any(token in symbol for token in TRIVIAL_SUFFIX_ALLOWED_CONTAINS_ANY):
        return True
    return False


def structurally_nontrivial(evidence: dict[str, Any] | None) -> bool:
    structural = dict(evidence or {})
    return bool(
        structural.get("source_body_complete")
        and int(structural.get("argument_count") or 0) >= 3
        and (structural.get("raises") or int(structural.get("return_paths") or 0) > 1)
    )


def receiver_state_accessor(evidence: dict[str, Any] | None) -> bool:
    structural = dict(evidence or {})
    return bool(
        structural.get("source_body_complete")
        and structural.get("owner_class")
        and int(structural.get("argument_count") or 0) == 0
        and not structural.get("called_operations")
        and not structural.get("observed_side_effects")
        and not structural.get("state_mutation")
        and int(structural.get("return_paths") or 0) == 1
    )


def liveness_probe_symbol(symbol: str) -> bool:
    return symbol in LIVENESS_PROBE_SYMBOLS


def bootstrap_support_symbol(path: str, symbol: str) -> bool:
    if symbol in BOOTSTRAP_SYMBOLS:
        return True
    if symbol.endswith("_args") and any(token in path for token in BOOTSTRAP_ARG_PATH_TOKENS):
        return True
    return False


def suspicious_hits(path: str, symbol: str) -> list[str]:
    hits = [token for token in SUSPICIOUS_PATH_TOKENS if token in path]
    hits.extend(token for token in SUSPICIOUS_SYMBOL_TOKENS if token in symbol)
    path_parts = {part for part in path.replace("\\", "/").split("/") if part}
    if path_parts.intersection(SUSPICIOUS_PATH_PARTS) and "icon" not in hits:
        hits.append("icon")
    return hits


def profiled_suspicious_allowed(suspicious: list[str], symbol: str, profiled_contract_family: bool) -> bool:
    if not profiled_contract_family:
        return False
    if suspicious == ["version"]:
        return symbol != "version" and symbol.endswith("_version")
    if suspicious == ["decorator"]:
        return "decorator" in symbol
    if suspicious == ["/helpers"]:
        return symbol in {"one_of", "oneof", "infix_notation", "located_expr"}
    if suspicious == ["/utils/"]:
        return symbol in {"parse_shorthand", "verifycert", "verify_certificate", "validate_certificate"}
    return False


def proven_bounded_helper(
    suspicious: list[str],
    reason_text: str,
    structural_evidence: dict[str, Any] | None,
    input_contract: dict[str, Any] | None,
    output_contract: dict[str, Any] | None,
    side_effect_contract: dict[str, Any] | None,
) -> bool:
    structural = dict(structural_evidence or {})
    return bool(
        suspicious == ["/helpers"]
        and "pure transform" in reason_text
        and structural.get("source_body_complete")
        and int(structural.get("argument_count") or 0) > 0
        and not structural.get("state_mutation")
        and not dict(side_effect_contract or {}).get("declared")
        and all_contract_shapes_concrete(dict(input_contract or {}), dict(output_contract or {}))
    )


def proven_bounded_policy(
    reason_text: str,
    structural_evidence: dict[str, Any] | None,
    output_contract: dict[str, Any] | None,
    side_effect_contract: dict[str, Any] | None,
) -> bool:
    structural = dict(structural_evidence or {})
    effects = set(dict(side_effect_contract or {}).get("declared") or [])
    output_types = {str(value).lower() for value in dict(output_contract or {}).values()}
    return bool(
        "bounded reproducible policy decision" in reason_text
        and "bool" in output_types
        and structural.get("source_body_complete")
        and not structural.get("state_mutation")
        and effects <= {"observability"}
    )


def generic_unprofiled_candidate(path: str, symbol: str) -> bool:
    if symbol in GENERIC_UNPROFILED_SYMBOLS:
        return True
    if not any(token in path for token in GENERIC_UNPROFILED_PATH_TOKENS):
        return False
    return any(token in symbol for token in GENERIC_UNPROFILED_SYMBOL_CONTAINS_ANY)


def special_boundary_adjustments(target: str, reason_text: str) -> dict[str, Any]:
    matched = []
    for value in TARGET_QUALITY_POLICY.get("special_boundaries", []):
        rule = dict(value or {})
        target_tokens = [str(token).lower() for token in rule.get("target_contains_any", [])]
        reason_tokens = [str(token).lower() for token in rule.get("reason_contains_any", [])]
        if target_tokens and not any(token in target for token in target_tokens):
            continue
        if reason_tokens and not any(token in reason_text for token in reason_tokens):
            continue
        matched.append(rule)
    return {
        "score_delta": sum(int(rule.get("score_bonus") or 0) for rule in matched),
        "reasons": [str(rule["reason"]) for rule in matched if rule.get("reason")],
        "allow_runtime": any(bool(rule.get("allow_runtime_boundary")) for rule in matched),
        "allow_meta": any(bool(rule.get("allow_meta_infrastructure")) for rule in matched),
    }
