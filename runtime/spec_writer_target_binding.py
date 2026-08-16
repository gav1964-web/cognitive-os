"""Config-backed standalone target eligibility for Spec Writer."""

from __future__ import annotations

from typing import Any

from .technical_spec_policy import load_technical_spec_policy


def standalone_target_eligibility(candidate: dict[str, Any]) -> dict[str, Any]:
    policy = dict(load_technical_spec_policy().get("target_binding_policy") or {})
    binding = str(candidate.get("target_binding") or "")
    blocked = {str(item) for item in list(policy.get("blocked_standalone_bindings") or [])}
    eligible = binding not in blocked
    reason_codes = dict(policy.get("blocked_reason_codes") or {})
    reasons = dict(policy.get("blocked_reasons") or {})
    return {
        "eligible": eligible,
        "target_binding": binding,
        "reason_code": "" if eligible else str(reason_codes.get(binding) or "unsupported_standalone_target_binding"),
        "reason": "" if eligible else str(reasons.get(binding) or "target binding is not standalone executable"),
        "policy": "technical_spec_policy.target_binding_policy",
    }


def dependency_readiness_adjustment(candidate: dict[str, Any]) -> tuple[int, list[str]]:
    policy = dict(load_technical_spec_policy().get("dependency_readiness") or {})
    readiness = dict(candidate.get("dependency_readiness") or {})
    missing = [str(item) for item in list(readiness.get("missing_external_modules") or []) if item]
    if not policy.get("enabled", True) or not missing:
        return 0, []
    if readiness.get("status") == "manifest_declared":
        return 0, ["project manifest declares missing imports; isolated executable probe remains required"]
    each = int(policy.get("missing_external_penalty_each") or 0)
    maximum = int(policy.get("max_missing_external_penalty") or 0)
    penalty = min(maximum, each * len(missing))
    prefix = str(policy.get("reason_prefix") or "runtime environment misses external imports")
    return -penalty, [f"{prefix}: {', '.join(missing[:6])}"]


def promote_environment_ready_candidate(ranked: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not ranked or _candidate_is_environment_ready(ranked[0]):
        return ranked
    policy = dict(load_technical_spec_policy().get("dependency_readiness") or {})
    slack = int(policy.get("environment_ready_reselection_score_slack") or 0)
    semantic_slack = int(policy.get("environment_ready_reselection_semantic_slack") or 0)
    first_score = int(ranked[0].get("score") or 0)
    first_semantic = int(ranked[0].get("semantic_score") or 0)
    alternatives = [
        item for item in ranked[1:]
        if _candidate_is_environment_ready(item) and int(item.get("score") or 0) >= first_score - slack
        and _preserves_semantic_quality(item, first_semantic=first_semantic, slack=semantic_slack)
    ]
    if not alternatives:
        return ranked
    selected = sorted(alternatives, key=lambda item: (-int(item.get("score") or 0), int(item.get("index") or 0)))[0]
    selected["reasons"] = [
        *list(selected.get("reasons") or []),
        "environment-ready candidate selected within configured score slack",
    ]
    return [selected, *[item for item in ranked if item is not selected]]


def _preserves_semantic_quality(item: dict[str, Any], *, first_semantic: int, slack: int) -> bool:
    candidate_semantic = int(item.get("semantic_score") or 0)
    return not first_semantic or not candidate_semantic or candidate_semantic >= first_semantic - slack


def _candidate_is_environment_ready(item: dict[str, Any]) -> bool:
    source = str(item.get("source") or "")
    readiness = dict(dict(item.get("evidence") or {}).get("dependency_readiness") or {})
    return ":" in source and readiness.get("status") == "ready"
