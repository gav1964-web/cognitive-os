"""Deterministic decision policy used before LLM layers exist."""

from __future__ import annotations

from .models import PolicyDecision
from .planner_stub import plan_recovery
from .registry import CapabilityRegistry


def decide(interrupt: dict[str, object], registry: CapabilityRegistry) -> PolicyDecision:
    decision = plan_recovery(interrupt, registry)
    if decision.action == "GENERATE_SPEC":
        return PolicyDecision(action="STOP", reason_code="GENERATE_SPEC_NOT_ENABLED_IN_MVP")
    return decision
