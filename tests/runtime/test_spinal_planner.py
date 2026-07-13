from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from runtime.layer_packets import intent_packet, interrupt_packet
from runtime.registry import CapabilityRegistry
from runtime.spinal_planner import adapt_from_interrupt_packet, plan_from_intent_packet
from runtime.spinal_quality import score_spinal_result


def _registry() -> CapabilityRegistry:
    root = Path(__file__).resolve().parents[2]
    registry = CapabilityRegistry(root)
    registry.reset_from_plugins()
    return registry


def test_spinal_planner_builds_deterministic_motor_plan() -> None:
    registry = _registry()
    intent = intent_packet(
        correlation_id="goal_spinal_1",
        intent="NORMALIZE_AND_HASH",
        objective="Normalize text then hash it",
        constraints={"route_goal": "normalize_then_hash"},
        expected_artifacts=["Pipeline"],
        success_criteria=["pipeline validates"],
    )

    result = plan_from_intent_packet(intent, registry)

    assert result["status"] == "planned"
    assert result["planner"] == "deterministic_graph_planner"
    assert result["pipeline"]["edges"] == [["normalize", "hash"]]
    assert result["motor_plan_packet"]["packet_type"] == "MOTOR_PLAN"
    assert result["motor_plan_packet"]["payload"]["capability_chain"] == ["normalize_text", "hash_payload"]
    assert result["motor_plan_packet"]["payload"]["execution_policy"]["execute_plugins"] is False
    assert result["signal_packet"]["payload"]["signals"][0]["type"] == "MOTOR_PLAN_READY"
    assert score_spinal_result(result, registry)["passed"] is True


def test_spinal_planner_uses_llm_only_as_validated_proposal() -> None:
    registry = _registry()
    intent = intent_packet(
        correlation_id="goal_spinal_2",
        intent="CUSTOM_CHAIN",
        objective="Select a nested value from JSON and hash it",
        constraints={},
        expected_artifacts=["Pipeline"],
        success_criteria=["pipeline validates"],
    )
    proposal = {
        "id": "llm_select_hash",
        "version": "0.1.0",
        "steps": [
            {"id": "select", "capability": "json_select", "input": {"data": "$input.data", "path": "$input.path"}},
            {"id": "hash", "capability": "hash_payload", "input": {"value": "$nodes.select.output.value"}},
        ],
        "retry_policy": {"max_attempts": 1, "retry_on": ["transient"]},
    }

    with patch("runtime.spinal_planner.plan_pipeline_with_llm") as planner:
        planner.return_value = {
            "status": "planned",
            "goal": "Select a nested value from JSON and hash it",
            "proposal": proposal,
            "pipeline": {
                "id": "llm_select_hash",
                "version": "0.1.0",
                "nodes": [
                    {"id": "select", "capability": "json_select", "input": {"data": "$input.data", "path": "$input.path"}},
                    {"id": "hash", "capability": "hash_payload", "input": {"value": "$nodes.select.output.value"}},
                ],
                "edges": [["select", "hash"]],
                "retry_policy": {"max_attempts": 1, "retry_on": ["transient"]},
            },
            "selection": [{"capability_id": "json_select"}, {"capability_id": "hash_payload"}],
        }
        result = plan_from_intent_packet(intent, registry, allow_local_llm=True)

    assert result["status"] == "planned"
    assert result["planner"] == "local_llm_graph_planner"
    assert result["pipeline"]["id"] == "llm_select_hash"
    assert result["motor_plan_packet"]["payload"]["validation"]["pipeline_dsl_validated"] is True
    assert score_spinal_result(result, registry)["passed"] is True


def test_spinal_planner_turns_interrupt_into_motor_signal() -> None:
    registry = _registry()
    interrupt = interrupt_packet(
        correlation_id="goal_spinal_3",
        interrupt={
            "type": "CRITICAL_INTERRUPT",
            "pipeline_id": "fetch_pipeline",
            "failed_node_id": "fetch",
            "error_class": "transient",
            "capability_id": "fetch_html",
            "error_fingerprint": {"exception_type": "TimeoutError", "traceback_hash": "test"},
            "state_ref": "checkpoint_test",
            "capability_status": "active",
            "suggested_actions": [],
        },
    )

    result = adapt_from_interrupt_packet(interrupt, registry)

    assert result["status"] == "adapted"
    assert result["decision"]["action"] == "RETRY"
    assert result["signal_packet"]["payload"]["needs_l4_decision"] is False
    assert result["signal_packet"]["payload"]["signals"][0]["type"] == "MOTOR_ADAPTATION"
