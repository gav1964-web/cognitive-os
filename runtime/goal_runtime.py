"""Vertical L4 -> L3.5 -> L2 runtime coordination."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .contract_registry import ContractRegistry
from .executor import execute_pipeline
from .layer_packets import signal_packet
from .local_inference import LocalInferenceConfig
from .models import Pipeline, PipelineNode, PolicyDecision
from .registry import CapabilityRegistry
from .spinal_planner import adapt_from_interrupt_packet, plan_from_intent_packet


class SpinalRecoveryController:
    """Bounded L2 interrupt handler shared by sync, async, and queued execution."""

    def __init__(self, *, max_adaptations: int = 2, packet_sink: Any = None) -> None:
        if max_adaptations < 0:
            raise ValueError("max_adaptations must be >= 0")
        self.max_adaptations = max_adaptations
        self.packet_sink = packet_sink
        self.adaptations: list[dict[str, Any]] = []
        self.signal_packets: list[dict[str, Any]] = []

    def __call__(self, interrupt: dict[str, Any], registry: CapabilityRegistry) -> PolicyDecision:
        if len(self.adaptations) >= self.max_adaptations:
            decision = PolicyDecision(action="STOP", reason_code="L35_ADAPTATION_BUDGET_EXHAUSTED")
            signal = signal_packet(
                correlation_id=str(interrupt["correlation_id"]),
                signals=[
                    {
                        "type": "MOTOR_ADAPTATION",
                        "action": "STOP",
                        "reason_code": decision.reason_code,
                    }
                ],
                needs_l4_decision=True,
                blocked=True,
            )
            adapted = {"status": "blocked", "decision": decision.__dict__, "signal_packet": signal}
        else:
            adapted = adapt_from_interrupt_packet(interrupt, registry)
            decision = PolicyDecision(**dict(adapted["decision"]))
        self.adaptations.append(adapted)
        signal = adapted.get("signal_packet")
        if isinstance(signal, dict):
            self.signal_packets.append(signal)
            if self.packet_sink is not None:
                self.packet_sink(signal)
        return decision


def plan_motor_route(
    intent: dict[str, Any],
    registry: CapabilityRegistry,
    *,
    required_capabilities: list[str] | None = None,
    memory_preflight: dict[str, Any] | None = None,
    allow_local_llm: bool = False,
    config: LocalInferenceConfig | None = None,
) -> dict[str, Any]:
    """Pass an L4 intent through the mandatory L3.5 planning facade."""

    contracts = ContractRegistry.from_capability_registry(registry)
    contracts.validate_layer_packet(intent)
    result = plan_from_intent_packet(
        intent,
        registry,
        required_capabilities=required_capabilities,
        memory_preflight=memory_preflight,
        allow_local_llm=allow_local_llm,
        config=config,
        memory_hint=_memory_hint(memory_preflight or {}),
    )
    signal = result.get("signal_packet")
    if isinstance(signal, dict):
        contracts.validate_layer_packet(signal)
    motor = result.get("motor_plan_packet")
    if isinstance(motor, dict):
        contracts.validate_layer_packet(motor)
    return result


def execute_motor_route(
    root: Path,
    spinal_result: dict[str, Any],
    root_input: dict[str, Any],
    registry: CapabilityRegistry,
    *,
    correlation_id: str,
    max_adaptations: int = 2,
) -> dict[str, Any]:
    """Execute a validated motor plan and route L2 interrupts back to L3.5."""

    if spinal_result.get("status") != "planned":
        raise ValueError("only a planned spinal result can be executed")
    motor = dict(spinal_result.get("motor_plan_packet") or {})
    ContractRegistry.from_capability_registry(registry).validate_layer_packet(motor)
    pipeline = _pipeline_from_dict(dict(spinal_result["pipeline"]))
    ContractRegistry.from_capability_registry(registry).validate_pipeline(pipeline)

    packets: list[dict[str, Any]] = []
    recovery = SpinalRecoveryController(max_adaptations=max_adaptations, packet_sink=packets.append)

    execution = execute_pipeline(
        root,
        pipeline,
        root_input,
        correlation_id=correlation_id,
        packet_sink=packets.append,
        recovery_handler=recovery,
    )
    return {
        "execution": execution,
        "layer_packets": packets,
        "adaptations": recovery.adaptations,
        "adaptation_count": len(recovery.adaptations),
        "adaptation_budget": max_adaptations,
    }


def _pipeline_from_dict(payload: dict[str, Any]) -> Pipeline:
    return Pipeline(
        id=str(payload["id"]),
        version=str(payload["version"]),
        nodes=[
            PipelineNode(id=str(node["id"]), capability=str(node["capability"]), input=dict(node["input"]))
            for node in payload["nodes"]
        ],
        edges=[list(edge) for edge in payload.get("edges", [])],
        retry_policy=dict(payload.get("retry_policy", {})),
    )


def _memory_hint(memory_preflight: dict[str, Any]) -> dict[str, Any]:
    return {
        "previous_plan": memory_preflight.get("recommendation"),
        "plan_template": memory_preflight.get("template_recommendation"),
    }
