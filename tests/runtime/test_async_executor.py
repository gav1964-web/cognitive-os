from __future__ import annotations

from pathlib import Path

import pytest

from runtime.async_executor import execute_pipeline_async
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
