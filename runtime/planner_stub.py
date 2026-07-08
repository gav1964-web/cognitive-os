"""Deterministic Level 3.5 planner stub.

This module intentionally contains no LLM calls. It is a replaceable boundary
where a local model can later translate interrupts into validated actions.
"""

from __future__ import annotations

import os

from .local_inference import LocalInferenceError, call_json_chat
from .models import PolicyDecision
from .registry import CapabilityRegistry


def plan_recovery(interrupt: dict[str, object], registry: CapabilityRegistry) -> PolicyDecision:
    if os.environ.get("COGNITIVE_OS_ENABLE_LOCAL_PLANNER", "").lower() in {"1", "true", "yes", "on"}:
        try:
            return _plan_with_local_inference(interrupt)
        except LocalInferenceError:
            pass
    error_class = str(interrupt["error_class"])
    capability_id = str(interrupt["capability_id"])
    if error_class == "transient":
        return PolicyDecision(action="RETRY", reason_code="L35_TRANSIENT_RETRY")
    if str(interrupt.get("capability_status")) == "quarantined":
        fallback = registry.find_fallback(capability_id)
        if fallback is not None:
            return PolicyDecision(
                action="SWITCH_PLUGIN",
                replacement_capability=fallback.id,
                reason_code="L35_COMPATIBLE_FALLBACK",
            )
        if "GENERATE_SPEC" in [str(item) for item in interrupt.get("suggested_actions", [])]:
            return PolicyDecision(action="GENERATE_SPEC", reason_code="L35_REBUILD_CANDIDATE_NEEDED")
    return PolicyDecision(action="STOP", reason_code="L35_NO_RECOVERY_ROUTE")


def _plan_with_local_inference(interrupt: dict[str, object]) -> PolicyDecision:
    result = call_json_chat(
        [
            {
                "role": "system",
                "content": (
                    "Return only JSON with keys action, replacement_capability, reason_code. "
                    "action must be RETRY, SWITCH_PLUGIN, GENERATE_SPEC, or STOP."
                ),
            },
            {"role": "user", "content": str(interrupt)},
        ]
    )
    action = str(result.get("action", "")).strip()
    if action not in {"RETRY", "SWITCH_PLUGIN", "GENERATE_SPEC", "STOP"}:
        raise LocalInferenceError(f"invalid planner action: {action}")
    replacement = result.get("replacement_capability")
    return PolicyDecision(
        action=action,
        replacement_capability=str(replacement) if replacement else None,
        reason_code=str(result.get("reason_code", "LOCAL_PLANNER")),
    )
