"""Typed packets for communication between Cognitive OS layers."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


SCHEMA_VERSION = "0.1"
PACKET_TYPES = {"INTENT", "MOTOR_PLAN", "SIGNAL", "EXECUTION_EVENT", "INTERRUPT", "REFLECTION"}
LAYER_ROUTES = {
    ("L4", "L3.5", "INTENT"),
    ("L3.5", "L4", "SIGNAL"),
    ("L3.5", "L2", "MOTOR_PLAN"),
    ("L2", "L3.5", "EXECUTION_EVENT"),
    ("L2", "L3.5", "INTERRUPT"),
    ("L4", "human", "REFLECTION"),
}


@dataclass(frozen=True)
class LayerPacket:
    packet_type: str
    source_layer: str
    target_layer: str
    correlation_id: str
    payload: dict[str, Any]
    schema_version: str = SCHEMA_VERSION
    packet_id: str = ""
    created_at: str = ""
    trace: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        packet = {
            "schema_version": self.schema_version,
            "packet_id": self.packet_id or _packet_id(self.packet_type, self.correlation_id, self.payload),
            "packet_type": self.packet_type,
            "source_layer": self.source_layer,
            "target_layer": self.target_layer,
            "created_at": self.created_at or _now(),
            "correlation_id": self.correlation_id,
            "payload": self.payload,
        }
        if self.trace:
            packet["trace"] = self.trace
        validate_packet(packet)
        return packet


def intent_packet(*, correlation_id: str, intent: str, objective: str, constraints: dict[str, Any], expected_artifacts: list[str], success_criteria: list[str]) -> dict[str, Any]:
    return LayerPacket(
        packet_type="INTENT",
        source_layer="L4",
        target_layer="L3.5",
        correlation_id=correlation_id,
        payload={
            "intent": intent,
            "objective": objective,
            "constraints": constraints,
            "expected_artifacts": expected_artifacts,
            "success_criteria": success_criteria,
        },
    ).to_dict()


def motor_plan_packet(*, correlation_id: str, planner: str, capability_chain: list[str], execution_policy: dict[str, Any], validation: dict[str, Any]) -> dict[str, Any]:
    return LayerPacket(
        packet_type="MOTOR_PLAN",
        source_layer="L3.5",
        target_layer="L2",
        correlation_id=correlation_id,
        payload={
            "planner": planner,
            "capability_chain": capability_chain,
            "execution_policy": execution_policy,
            "validation": validation,
        },
    ).to_dict()


def signal_packet(*, correlation_id: str, signals: list[dict[str, Any]], needs_l4_decision: bool = False, blocked: bool = False) -> dict[str, Any]:
    return LayerPacket(
        packet_type="SIGNAL",
        source_layer="L3.5",
        target_layer="L4",
        correlation_id=correlation_id,
        payload={"signals": signals, "needs_l4_decision": needs_l4_decision, "blocked": blocked},
    ).to_dict()


def execution_event_packet(*, correlation_id: str, event_type: str, pipeline_id: str, node_id: str, capability_id: str, status: str, artifact_refs: dict[str, Any] | None = None) -> dict[str, Any]:
    return LayerPacket(
        packet_type="EXECUTION_EVENT",
        source_layer="L2",
        target_layer="L3.5",
        correlation_id=correlation_id,
        payload={
            "event_type": event_type,
            "pipeline_id": pipeline_id,
            "node_id": node_id,
            "capability_id": capability_id,
            "status": status,
            "artifact_refs": artifact_refs or {},
        },
    ).to_dict()


def interrupt_packet(*, correlation_id: str, interrupt: dict[str, Any]) -> dict[str, Any]:
    return LayerPacket(
        packet_type="INTERRUPT",
        source_layer="L2",
        target_layer="L3.5",
        correlation_id=correlation_id,
        payload=interrupt,
    ).to_dict()


def validate_packet(packet: dict[str, Any]) -> None:
    required = {"schema_version", "packet_id", "packet_type", "source_layer", "target_layer", "created_at", "correlation_id", "payload"}
    missing = sorted(required - set(packet))
    if missing:
        raise ValueError(f"layer packet missing keys: {', '.join(missing)}")
    if packet["schema_version"] != SCHEMA_VERSION:
        raise ValueError(f"unsupported layer packet schema_version: {packet['schema_version']}")
    if packet["packet_type"] not in PACKET_TYPES:
        raise ValueError(f"unsupported layer packet_type: {packet['packet_type']}")
    route = (str(packet["source_layer"]), str(packet["target_layer"]), str(packet["packet_type"]))
    if route not in LAYER_ROUTES:
        raise ValueError(f"unsupported layer packet route: {route}")
    if not isinstance(packet["payload"], dict):
        raise ValueError("layer packet payload must be an object")
    _validate_payload(packet)


def _validate_payload(packet: dict[str, Any]) -> None:
    payload = dict(packet["payload"])
    packet_type = packet["packet_type"]
    if packet_type == "INTENT":
        _require_payload(payload, {"intent", "objective", "constraints", "expected_artifacts", "success_criteria"})
    elif packet_type == "MOTOR_PLAN":
        _require_payload(payload, {"planner", "capability_chain", "execution_policy", "validation"})
    elif packet_type == "SIGNAL":
        _require_payload(payload, {"signals", "needs_l4_decision", "blocked"})
    elif packet_type == "EXECUTION_EVENT":
        _require_payload(payload, {"event_type", "pipeline_id", "node_id", "capability_id", "status", "artifact_refs"})
    elif packet_type == "INTERRUPT":
        _require_payload(
            payload,
            {
                "type",
                "pipeline_id",
                "failed_node_id",
                "capability_id",
                "error_class",
                "error_fingerprint",
                "state_ref",
                "capability_status",
                "suggested_actions",
            },
        )


def _require_payload(payload: dict[str, Any], required: set[str]) -> None:
    missing = sorted(required - set(payload))
    if missing:
        raise ValueError(f"layer packet payload missing keys: {', '.join(missing)}")


def _packet_id(packet_type: str, correlation_id: str, payload: dict[str, Any]) -> str:
    seed = f"{packet_type}:{correlation_id}:{repr(sorted(payload.items()))}:{_now()}"
    digest = hashlib.sha256(seed.encode("utf-8", errors="replace")).hexdigest()[:12]
    return f"pkt_{digest}"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
