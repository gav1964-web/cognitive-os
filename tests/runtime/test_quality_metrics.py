from __future__ import annotations

import json
from pathlib import Path

from runtime.executor import execute_pipeline
from runtime.models import Pipeline, PipelineNode
from runtime.registry import CapabilityRegistry


def test_execution_updates_quality_metrics():
    root = Path(__file__).resolve().parents[2]
    CapabilityRegistry(root).reset_from_plugins()
    pipeline = Pipeline(
        id="quality_hash",
        version="0.1.0",
        nodes=[PipelineNode(id="hash", capability="hash_payload", input={"value": "$input.value"})],
        edges=[],
        retry_policy={},
    )

    execute_pipeline(root, pipeline, {"value": "quality"})

    metrics = json.loads((root / "artifacts" / "registry" / "quality.json").read_text(encoding="utf-8"))
    assert metrics["hash_payload"]["runs"] >= 1
    assert metrics["hash_payload"]["successes"] >= 1
