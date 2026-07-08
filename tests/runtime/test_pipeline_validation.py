from __future__ import annotations

from pathlib import Path

import pytest

from runtime.models import Pipeline, PipelineNode
from runtime.pipeline import PipelineValidationError, load_pipeline, validate_pipeline
from runtime.registry import CapabilityRegistry


@pytest.fixture()
def registry():
    root = Path(__file__).resolve().parents[2]
    reg = CapabilityRegistry(root)
    reg.reset_from_plugins()
    return reg


def test_pipeline_validation_accepts_current_pipeline(registry):
    pipeline = load_pipeline(Path(__file__).resolve().parents[2] / "pipelines" / "fetch_parse_save.json")
    validate_pipeline(pipeline, registry)


def test_pipeline_validation_rejects_missing_capability(registry):
    pipeline = Pipeline(
        id="bad",
        version="0.1.0",
        nodes=[PipelineNode(id="x", capability="missing", input={})],
        edges=[],
        retry_policy={},
    )
    with pytest.raises(PipelineValidationError, match="missing capability"):
        validate_pipeline(pipeline, registry)


def test_pipeline_validation_accepts_branching_dag(registry):
    pipeline = Pipeline(
        id="branching",
        version="0.1.0",
        nodes=[
            PipelineNode(id="normalize", capability="normalize_text", input={"text": "$input.text"}),
            PipelineNode(id="hash_a", capability="hash_payload", input={"value": "$nodes.normalize.output.text"}),
            PipelineNode(id="hash_b", capability="hash_payload", input={"value": "$input.other"}),
        ],
        edges=[["normalize", "hash_a"]],
        retry_policy={},
    )
    validate_pipeline(pipeline, registry)


def test_pipeline_validation_rejects_reference_without_dependency_edge(registry):
    pipeline = Pipeline(
        id="bad",
        version="0.1.0",
        nodes=[
            PipelineNode(id="a", capability="fetch_html", input={"url": "$input.url"}),
            PipelineNode(id="b", capability="parse_title", input={"html": "$nodes.a.output.html"}),
        ],
        edges=[],
        retry_policy={},
    )
    with pytest.raises(PipelineValidationError, match="without a dependency edge"):
        validate_pipeline(pipeline, registry)


def test_pipeline_validation_rejects_cycles(registry):
    pipeline = Pipeline(
        id="bad",
        version="0.1.0",
        nodes=[
            PipelineNode(id="a", capability="normalize_text", input={"text": "$nodes.b.output.text"}),
            PipelineNode(id="b", capability="normalize_text", input={"text": "$nodes.a.output.text"}),
        ],
        edges=[["a", "b"], ["b", "a"]],
        retry_policy={},
    )
    with pytest.raises(PipelineValidationError, match="cycle"):
        validate_pipeline(pipeline, registry)
