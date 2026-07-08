from __future__ import annotations

from pathlib import Path

import pytest

from runtime.executor import execute_pipeline
from runtime.pipeline import load_pipeline
from runtime.registry import CapabilityRegistry


@pytest.fixture()
def workspace_root():
    root = Path(__file__).resolve().parents[2]
    CapabilityRegistry(root).reset_from_plugins()
    yield root
    CapabilityRegistry(root).reset_from_plugins()


def test_happy_path_completes_all_nodes(workspace_root):
    pipeline = load_pipeline(workspace_root / "pipelines" / "fetch_parse_save.json")

    result = execute_pipeline(
        workspace_root,
        pipeline,
        {"url": "mock://ok", "output_path": "artifacts/outputs/test_happy.json"},
    )

    assert result["status"] == "ok"
    assert result["completed_nodes"] == ["fetch", "parse", "save"]
    assert result["outputs"]["parse"] == {"title": "Cognitive OS MVP"}


def test_dependency_error_quarantines_and_switches_to_fallback(workspace_root):
    pipeline = load_pipeline(workspace_root / "pipelines" / "fetch_parse_save.json")

    result = execute_pipeline(
        workspace_root,
        pipeline,
        {"url": "mock://broken_dependency", "output_path": "artifacts/outputs/test_quarantine.json"},
    )

    registry = CapabilityRegistry(workspace_root)
    registry.load()
    assert result["status"] == "ok"
    assert result["completed_nodes"] == ["fetch", "parse", "save"]
    assert result["outputs"]["parse"] == {"title": "recovered by fallback"}
    assert registry.capabilities["parse_title"].lifecycle_status == "quarantined"
    assert (workspace_root / "artifacts" / "failures" / "events.jsonl").exists()


def test_no_fallback_stops_with_interrupt(workspace_root):
    registry = CapabilityRegistry(workspace_root)
    registry.load()
    registry.mark_status("parse_title_fallback", "retired")
    pipeline = load_pipeline(workspace_root / "pipelines" / "fetch_parse_save.json")

    result = execute_pipeline(
        workspace_root,
        pipeline,
        {"url": "mock://broken_dependency", "output_path": "artifacts/outputs/test_no_fallback.json"},
    )

    assert result["status"] == "stopped"
    assert result["completed_nodes"] == ["fetch"]
    assert result["interrupt"]["error_class"] == "dependency_error"
    assert result["interrupt"]["capability_status"] == "quarantined"
    assert result["decision"]["action"] == "STOP"


def test_registry_save_is_atomic_and_loadable(workspace_root):
    registry = CapabilityRegistry(workspace_root)
    registry.load()
    registry.mark_status("parse_title", "quarantined")

    reloaded = CapabilityRegistry(workspace_root)
    reloaded.load()

    assert reloaded.capabilities["parse_title"].lifecycle_status == "quarantined"
    assert not (workspace_root / "registry" / "capabilities.json.tmp").exists()
