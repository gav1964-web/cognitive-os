"""Quality checks for Layer 3.5 motor planning results."""

from __future__ import annotations

from typing import Any

from .registry import CapabilityRegistry


def score_spinal_result(result: dict[str, Any], registry: CapabilityRegistry) -> dict[str, Any]:
    checks = {
        "typed_packets": _has_typed_packets(result),
        "validated_pipeline": _has_validated_pipeline(result),
        "known_capabilities": _uses_known_capabilities(result, registry),
        "no_direct_execution": _does_not_execute(result),
        "bounded_escalation": _bounded_escalation(result),
    }
    score = sum(1 for passed in checks.values() if passed) / len(checks)
    return {
        "score": round(score, 3),
        "passed": score == 1.0,
        "checks": checks,
    }


def _has_typed_packets(result: dict[str, Any]) -> bool:
    if result.get("status") == "planned":
        motor = result.get("motor_plan_packet")
        signal = result.get("signal_packet")
        return (
            isinstance(motor, dict)
            and motor.get("packet_type") == "MOTOR_PLAN"
            and motor.get("source_layer") == "L3.5"
            and motor.get("target_layer") == "L2"
            and isinstance(signal, dict)
            and signal.get("packet_type") == "SIGNAL"
            and signal.get("source_layer") == "L3.5"
        )
    signal = result.get("signal_packet")
    return isinstance(signal, dict) and signal.get("packet_type") == "SIGNAL"


def _has_validated_pipeline(result: dict[str, Any]) -> bool:
    if result.get("status") != "planned":
        return True
    validation = dict(result.get("motor_plan_packet", {}).get("payload", {}).get("validation", {}))
    return validation.get("pipeline_dsl_validated") is True and validation.get("registry_validated") is True


def _uses_known_capabilities(result: dict[str, Any], registry: CapabilityRegistry) -> bool:
    if result.get("status") != "planned":
        return True
    chain = list(result.get("motor_plan_packet", {}).get("payload", {}).get("capability_chain", []))
    return bool(chain) and all(str(capability_id) in registry.capabilities for capability_id in chain)


def _does_not_execute(result: dict[str, Any]) -> bool:
    if result.get("status") != "planned":
        return True
    policy = dict(result.get("motor_plan_packet", {}).get("payload", {}).get("execution_policy", {}))
    return policy.get("execute_plugins") is False


def _bounded_escalation(result: dict[str, Any]) -> bool:
    signal_payload = dict(result.get("signal_packet", {}).get("payload", {}))
    if result.get("status") == "planned":
        return signal_payload.get("needs_l4_decision") is False and signal_payload.get("blocked") is False
    if result.get("status") == "blocked":
        return signal_payload.get("needs_l4_decision") is True and signal_payload.get("blocked") is True
    return True
