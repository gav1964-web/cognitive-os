from __future__ import annotations

import pytest

from runtime.layer_packets import intent_packet, motor_plan_packet, signal_packet, validate_packet


def test_layer_packets_build_valid_typed_envelopes():
    intent = intent_packet(
        correlation_id="goal_1",
        intent="ANALYZE_PROJECT",
        objective="Analyze project",
        constraints={"read_only": True},
        expected_artifacts=["project_map_report"],
        success_criteria=["report exists"],
    )
    motor = motor_plan_packet(
        correlation_id="goal_1",
        planner="deterministic_required_capabilities",
        capability_chain=["scan_project_tree", "project_map_report"],
        execution_policy={"checkpoint_after": ["scan_project_tree"]},
        validation={"pipeline_dsl_validated": True},
    )
    signal = signal_packet(
        correlation_id="goal_1",
        signals=[{"type": "IDEMPOTENCY_RISK", "target": "app.py:save"}],
    )

    assert intent["packet_type"] == "INTENT"
    assert motor["source_layer"] == "L3.5"
    assert signal["target_layer"] == "L4"


def test_layer_packet_rejects_wrong_route():
    packet = intent_packet(
        correlation_id="goal_1",
        intent="ANALYZE_PROJECT",
        objective="Analyze project",
        constraints={},
        expected_artifacts=[],
        success_criteria=[],
    )
    packet["target_layer"] = "L2"

    with pytest.raises(ValueError, match="unsupported layer packet route"):
        validate_packet(packet)
