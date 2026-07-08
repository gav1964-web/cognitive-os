from __future__ import annotations

from pathlib import Path

from runtime.checkpoint import save_checkpoint
from runtime.executor import resume_pipeline
from runtime.models import ExecutionContext, Pipeline, PipelineNode
from runtime.registry import CapabilityRegistry


def test_resume_pipeline_continues_after_completed_nodes():
    root = Path(__file__).resolve().parents[2]
    CapabilityRegistry(root).reset_from_plugins()
    pipeline = Pipeline(
        id="resume_hash",
        version="0.1.0",
        nodes=[
            PipelineNode(id="normalize", capability="normalize_text", input={"text": "$input.text"}),
            PipelineNode(id="hash", capability="hash_payload", input={"value": "$nodes.normalize.output.text"}),
        ],
        edges=[["normalize", "hash"]],
        retry_policy={"max_attempts": 1},
    )
    context = ExecutionContext(
        pipeline=pipeline,
        root_input={"text": " hello   resume "},
        state="PAUSED",
        current_node="hash",
        completed_nodes=["normalize"],
        node_outputs={"normalize": {"text": "hello resume"}},
    )
    checkpoint_id = save_checkpoint(root, context, registry_hash="sha256:test")

    result = resume_pipeline(root, checkpoint_id, pipeline=pipeline)

    assert result["status"] == "ok"
    assert result["completed_nodes"] == ["normalize", "hash"]
    assert "hash" in result["outputs"]["hash"]
    assert (root / "artifacts" / "execution" / "journal.jsonl").exists()
