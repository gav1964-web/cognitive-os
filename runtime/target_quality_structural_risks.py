"""Config-driven structural risks that cap first-slice quality."""

from __future__ import annotations

from typing import Any

from .target_quality_policy import policy_tokens, target_quality_section


POLICY = target_quality_section("target_quality")
CONSTANT_HOOK_PREFIXES = policy_tokens(POLICY, "constant_return_hook_prefixes")
CONSTANT_HOOK_SCORE_CAP = int(policy_tokens(POLICY, "constant_return_hook_score_cap")[0])
CONSTANT_HOOK_REASON = policy_tokens(POLICY, "constant_return_hook_reason")[0]
UNMODELED_EFFECT_SCORE_CAP = int(policy_tokens(POLICY, "unmodeled_effect_score_cap")[0])
UNMODELED_EFFECT_REASON = policy_tokens(POLICY, "unmodeled_effect_reason")[0]


def apply_structural_risk_caps(
    score: int,
    symbol: str,
    structural_evidence: dict[str, Any] | None,
    profiled_contract_family: bool,
    side_effect_contract: dict[str, Any] | None = None,
) -> tuple[int, list[str]]:
    leaf_symbol = symbol.rsplit(".", 1)[-1]
    constant_hook = bool(
        dict(structural_evidence or {}).get("literal_return_only")
        and any(leaf_symbol.startswith(prefix) for prefix in CONSTANT_HOOK_PREFIXES)
    )
    reasons = []
    if constant_hook and not profiled_contract_family:
        score = min(score, CONSTANT_HOOK_SCORE_CAP)
        reasons.append(CONSTANT_HOOK_REASON)
    observed = set(dict(structural_evidence or {}).get("observed_side_effects") or [])
    declared = set(dict(side_effect_contract or {}).get("declared") or [])
    unmodeled = sorted(str(effect) for effect in observed - declared)
    if unmodeled:
        score = min(score, UNMODELED_EFFECT_SCORE_CAP)
        reasons.append(UNMODELED_EFFECT_REASON.format(effects=", ".join(unmodeled)))
    return score, reasons
