from __future__ import annotations

from pathlib import Path

from runtime.executor import execute_pipeline
from runtime.pipeline import load_pipeline
from runtime.registry import CapabilityRegistry


def test_transient_error_retries_and_marks_capability_degraded():
    root = Path(__file__).resolve().parents[2]
    CapabilityRegistry(root).reset_from_plugins()
    pipeline = load_pipeline(root / "pipelines" / "fetch_parse_save.json")

    result = execute_pipeline(
        root,
        pipeline,
        {"url": "mock://transient_once", "output_path": "artifacts/outputs/transient_retry.json"},
    )

    registry = CapabilityRegistry(root)
    registry.load()
    assert result["status"] == "ok"
    assert result["outputs"]["parse"] == {"title": "Recovered After Retry"}
    assert registry.capabilities["fetch_html"].lifecycle_status == "degraded"
