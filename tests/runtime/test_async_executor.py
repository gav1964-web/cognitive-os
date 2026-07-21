from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from runtime.async_executor import execute_pipeline_async
from runtime.goal_runtime import SpinalRecoveryController
from runtime.models import Pipeline, PipelineNode
from runtime.pipeline import load_pipeline
from runtime.registry import CapabilityRegistry


@pytest.mark.asyncio
async def test_async_executor_runs_happy_path():
    root = Path(__file__).resolve().parents[2]
    CapabilityRegistry(root).reset_from_plugins()
    pipeline = load_pipeline(root / "pipelines" / "fetch_parse_save.json")

    result = await execute_pipeline_async(
        root,
        pipeline,
        {"url": "mock://ok", "output_path": "artifacts/outputs/async_happy.json"},
    )

    assert result["status"] == "ok"
    assert result["completed_nodes"] == ["fetch", "parse", "save"]


@pytest.mark.asyncio
async def test_async_executor_runs_branching_dag():
    root = Path(__file__).resolve().parents[2]
    CapabilityRegistry(root).reset_from_plugins()
    pipeline = Pipeline(
        id="branching",
        version="0.1.0",
        nodes=[
            PipelineNode(id="normalize", capability="normalize_text", input={"text": "$input.text"}),
            PipelineNode(id="hash_raw", capability="hash_payload", input={"value": "$input.text"}),
            PipelineNode(id="hash_normalized", capability="hash_payload", input={"value": "$nodes.normalize.output.text"}),
        ],
        edges=[["normalize", "hash_normalized"]],
        retry_policy={"max_attempts": 1, "retry_on": ["transient"], "node_timeout_seconds": 5},
    )

    result = await execute_pipeline_async(root, pipeline, {"text": "  hello   world  "})

    assert result["status"] == "ok"
    assert set(result["completed_nodes"]) == {"normalize", "hash_raw", "hash_normalized"}
    assert result["outputs"]["normalize"] == {"text": "hello world"}


@pytest.mark.asyncio
async def test_async_executor_emits_packets_and_recovers_through_spinal_layer():
    root = Path(__file__).resolve().parents[2]
    CapabilityRegistry(root).reset_from_plugins()


@pytest.mark.asyncio
async def test_async_executor_blocks_when_fallback_also_fails():
    root = Path(__file__).resolve().parents[2]
    CapabilityRegistry(root).reset_from_plugins()
    pipeline = load_pipeline(root / "pipelines" / "fetch_parse_save.json")
    packets = []
    recovery = SpinalRecoveryController(max_adaptations=1, packet_sink=packets.append)
    from runtime.async_executor import _execute_node as real_execute_node

    def fail_fallback(*args, **kwargs):
        if args[2] == "parse_title_fallback":
            raise ImportError("simulated async fallback failure")
        return real_execute_node(*args, **kwargs)

    with patch("runtime.async_executor._execute_node", side_effect=fail_fallback):
        result = await execute_pipeline_async(
            root,
            pipeline,
            {"url": "mock://broken_dependency", "output_path": "artifacts/outputs/async_multi_failure.json"},
            correlation_id="async_multi_failure",
            packet_sink=packets.append,
            recovery_handler=recovery,
        )

    assert result["status"] == "stopped"
    assert result["decision"]["reason_code"] == "L35_ADAPTATION_BUDGET_EXHAUSTED"
    interrupts = [packet for packet in packets if packet["packet_type"] == "INTERRUPT"]
    assert [packet["payload"]["capability_id"] for packet in interrupts] == [
        "parse_title",
        "parse_title_fallback",
    ]
    assert any(
        packet["packet_type"] == "SIGNAL" and packet["payload"]["blocked"] is True
        for packet in packets
    )
    CapabilityRegistry(root).reset_from_plugins()
    pipeline = load_pipeline(root / "pipelines" / "fetch_parse_save.json")
    packets = []
    recovery = SpinalRecoveryController(packet_sink=packets.append)

    result = await execute_pipeline_async(
        root,
        pipeline,
        {"url": "mock://broken_dependency", "output_path": "artifacts/outputs/async_recovery.json"},
        correlation_id="async_recovery",
        packet_sink=packets.append,
        recovery_handler=recovery,
    )

    assert result["status"] == "ok"
    assert result["outputs"]["parse"] == {"title": "recovered by fallback"}
    assert recovery.adaptations[0]["decision"]["action"] == "SWITCH_PLUGIN"
    assert any(packet["packet_type"] == "INTERRUPT" for packet in packets)
    assert any(
        packet["packet_type"] == "EXECUTION_EVENT"
        and packet["payload"]["event_type"] == "NODE_RECOVERED"
        for packet in packets
    )
    assert all(packet["correlation_id"] == "async_recovery" for packet in packets)
    CapabilityRegistry(root).reset_from_plugins()
