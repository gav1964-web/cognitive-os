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
    each = int(policy.get("missing_external_penalty_each") or 0)
    maximum = int(policy.get("max_missing_external_penalty") or 0)
    penalty = min(maximum, each * len(missing))
    prefix = str(policy.get("reason_prefix") or "runtime environment misses external imports")
    return -penalty, [f"{prefix}: {', '.join(missing[:6])}"]
