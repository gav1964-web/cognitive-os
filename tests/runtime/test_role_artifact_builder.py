from __future__ import annotations

import json

import pytest

from runtime.role_artifact_builder import ArtifactBuilderError, load_artifact_builders
from runtime.role_artifact_interpreter import load_role_artifact_pipeline


def test_artifact_builders_are_loaded_from_external_config():
    builders = load_artifact_builders()

    assert "architecture_decision_v1" in builders
    assert builders["architecture_decision_v1"]["artifact_type"] == "ArchitectureDecisionRecord"


def test_artifact_builder_loader_rejects_bad_schema(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"schema_version": "bad", "builders": {}}), encoding="utf-8")

    with pytest.raises(ArtifactBuilderError):
        load_artifact_builders(str(path))


def test_role_pipeline_uses_generic_builder_dispatcher():
    pipeline = load_role_artifact_pipeline()

    assert {
        step["builder"] for step in pipeline["steps"]
    } == {"runtime.role_artifact_builder:build_configured_artifact"}
    assert all("builder_id" in step["bindings"] for step in pipeline["steps"])
