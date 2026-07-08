from __future__ import annotations

from pathlib import Path

from runtime.executor import execute_pipeline
from runtime.models import Pipeline, PipelineNode
from runtime.registry import CapabilityRegistry


def test_process_boundary_executes_plugin_in_child_process():
    root = Path(__file__).resolve().parents[2]
    CapabilityRegistry(root).reset_from_plugins()
    pipeline = Pipeline(
        id="process_hash",
        version="0.1.0",
        nodes=[PipelineNode(id="hash", capability="hash_payload", input={"value": "$input.value"})],
        edges=[],
        retry_policy={"process_boundary": True, "node_timeout_seconds": 5},
    )

    result = execute_pipeline(root, pipeline, {"value": {"hello": "process"}})

    assert result["status"] == "ok"
    assert result["completed_nodes"] == ["hash"]
    assert result["outputs"]["hash"]["hash"].startswith("sha256:")
