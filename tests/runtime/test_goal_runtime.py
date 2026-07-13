from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from runtime.goal_runtime import SpinalRecoveryController, execute_motor_route, plan_motor_route
from runtime.layer_packets import intent_packet, interrupt_packet
from runtime.registry import CapabilityRegistry


@pytest.fixture()
def root_and_registry():
    root = Path(__file__).resolve().parents[2]
    registry = CapabilityRegistry(root)
    registry.reset_from_plugins()
    yield root, registry
    CapabilityRegistry(root).reset_from_plugins()


def _intent(correlation_id: str, objective: str, required: list[str]):
    return intent_packet(
        correlation_id=correlation_id,
        intent="PLAN_KNOWN_ROUTE",
        objective=objective,
        constraints={"required_capabilities": required},
        expected_artifacts=[],
        success_criteria=["pipeline completes"],
    )


def test_vertical_runtime_emits_motor_and_execution_packets(root_and_registry):
    root, registry = root_and_registry
    intent = _intent("goal_vertical_ok", "Normalize and hash text", ["normalize_text", "hash_payload"])

    planned = plan_motor_route(intent, registry, required_capabilities=["normalize_text", "hash_payload"])
    result = execute_motor_route(
        root,
        planned,
        {"text": "  hello   world  "},
        registry,
        correlation_id="goal_vertical_ok",
    )

    assert planned["motor_plan_packet"]["packet_type"] == "MOTOR_PLAN"
    assert result["execution"]["status"] == "ok"
    events = [packet for packet in result["layer_packets"] if packet["packet_type"] == "EXECUTION_EVENT"]
    assert [packet["payload"]["event_type"] for packet in events] == [
        "NODE_STARTED",
        "NODE_COMPLETED",
        "NODE_STARTED",
        "NODE_COMPLETED",
    ]
    assert all(packet["correlation_id"] == "goal_vertical_ok" for packet in events)


def test_vertical_runtime_routes_interrupt_to_spinal_adaptation(root_and_registry):
    root, registry = root_and_registry
    intent = _intent(
        "goal_vertical_recovery",
        "Fetch, parse, and save",
        ["fetch_html", "parse_title", "save_json"],
    )
    planned = plan_motor_route(
        intent,
        registry,
        required_capabilities=["fetch_html", "parse_title", "save_json"],
    )

    result = execute_motor_route(
        root,
        planned,
        {
            "url": "mock://broken_dependency",
            "output_path": "artifacts/outputs/vertical_recovery.json",
        },
        registry,
        correlation_id="goal_vertical_recovery",
    )

    assert result["execution"]["status"] == "ok"
    assert result["adaptation_count"] == 1
    assert result["adaptations"][0]["decision"]["action"] == "SWITCH_PLUGIN"
    packet_types = [packet["packet_type"] for packet in result["layer_packets"]]
    assert "INTERRUPT" in packet_types
    assert "SIGNAL" in packet_types
    assert any(
        packet["packet_type"] == "EXECUTION_EVENT"
        and packet["payload"]["event_type"] == "NODE_RECOVERED"
        for packet in result["layer_packets"]
    )


def test_recovery_controller_emits_blocked_signal_when_budget_is_zero(root_and_registry):
    _, registry = root_and_registry
    packets = []
    recovery = SpinalRecoveryController(max_adaptations=0, packet_sink=packets.append)
    interrupt = interrupt_packet(
        correlation_id="goal_budget_zero",
        interrupt={
            "type": "CRITICAL_INTERRUPT",
            "pipeline_id": "pipeline",
            "failed_node_id": "node",
            "capability_id": "fetch_html",
            "error_class": "transient",
            "error_fingerprint": {"exception_type": "TimeoutError", "traceback_hash": "test"},
            "state_ref": "checkpoint",
            "capability_status": "active",
            "suggested_actions": ["RETRY", "STOP"],
        },
    )

    decision = recovery(interrupt, registry)

    assert decision.action == "STOP"
    assert decision.reason_code == "L35_ADAPTATION_BUDGET_EXHAUSTED"
    assert packets[0]["packet_type"] == "SIGNAL"
    assert packets[0]["payload"]["blocked"] is True


def test_vertical_runtime_blocks_after_primary_and_fallback_fail(root_and_registry):
    root, registry = root_and_registry
    intent = _intent(
        "goal_multi_failure",
        "Fetch, parse, and save",
        ["fetch_html", "parse_title", "save_json"],
    )
    planned = plan_motor_route(
        intent,
        registry,
        required_capabilities=["fetch_html", "parse_title", "save_json"],
    )
    from runtime.executor import _execute_node as real_execute_node

    def fail_fallback(*args, **kwargs):
        capability_id = args[2]
        if capability_id == "parse_title_fallback":
            raise ImportError("simulated fallback dependency failure")
        return real_execute_node(*args, **kwargs)

    with patch("runtime.executor._execute_node", side_effect=fail_fallback):
        result = execute_motor_route(
            root,
            planned,
            {
                "url": "mock://broken_dependency",
                "output_path": "artifacts/outputs/multi_failure.json",
            },
            registry,
            correlation_id="goal_multi_failure",
            max_adaptations=1,
        )

    assert result["execution"]["status"] == "stopped"
    assert result["execution"]["decision"]["reason_code"] == "L35_ADAPTATION_BUDGET_EXHAUSTED"
    assert result["adaptation_count"] == 2
    assert result["adaptations"][0]["decision"]["action"] == "SWITCH_PLUGIN"
    assert result["adaptations"][1]["status"] == "blocked"
    interrupts = [packet for packet in result["layer_packets"] if packet["packet_type"] == "INTERRUPT"]
    assert [packet["payload"]["capability_id"] for packet in interrupts] == [
        "parse_title",
        "parse_title_fallback",
    ]
    blocked_signals = [
        packet
        for packet in result["layer_packets"]
        if packet["packet_type"] == "SIGNAL" and packet["payload"]["blocked"] is True
    ]
    assert len(blocked_signals) == 1
