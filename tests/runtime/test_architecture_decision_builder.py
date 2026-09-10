from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from runtime.architecture_decision_builder import _contract_targets, build_architecture_decision
from runtime._parts.architecture_decision_builder_part3 import _provider_parser_sources


def test_provider_parser_discovery_tolerates_unreadable_project_tree(tmp_path):
    with patch.object(Path, "rglob", side_effect=FileNotFoundError("vanished path")):
        assert _provider_parser_sources(tmp_path) == []


def test_script_product_fallback_is_kept_as_contract_target():
    source = "scripts/upgrade-config.py:render_config"
    context = {source: {"signature": {"args": [{"name": "parsed"}]}, "side_effects": []}}

    targets = _contract_targets([source], context)

    assert [row["source"] for row in targets] == [source]


def test_architecture_decision_does_not_handoff_test_only_sources_as_implementation_targets(tmp_path):
    project = tmp_path / "rust_python_package"
    project.mkdir()
    (project / "test").mkdir()
    (project / "test" / "test_default.py").write_text("def test_default_not_callable():\n    pass\n", encoding="utf-8")

    adr = build_architecture_decision(
        goal="Analyze package with no safe Python implementation target",
        project_report={
            "summary": {"root": project.as_posix(), "file_count": 1, "entrypoints": [], "languages": ["Python"]},
            "answers": {
                "1_scope": {
                    "main_task": "Expose a Python package backed by non-Python implementation.",
                    "inputs": ["Python caller objects"],
                    "outputs": ["serialized values"],
                    "code_areas": {"tests": ["test/test_default.py"]},
                },
                "6_runtime_extraction_readiness": {
                    "minimal_extraction_plan": {
                        "capabilities_to_extract": [],
                        "blocked_by": ["no_safe_python_candidate"],
                    }
                },
            },
            "analysis_tasks": {
                "tasks": [
                    {
                        "type": "DRAFT_PIPELINE_CAPABILITY",
                        "target": "test/test_default.py:test_default_not_callable",
                        "acceptance": "Capability candidate requires TechnicalSpec.",
                    }
                ]
            },
            "architecture_synthesis": {
                "artifact_type": "ProjectArchitectureSynthesis",
                "recommended_first_slice": {
                    "name": "automation_task_execution_slice",
                    "goal": "No implementation target exists.",
                    "targets": [],
                    "steps": ["Stop until a source-backed implementation target exists."],
                },
            },
        },
    )

    brief = adr["spec_writer_brief"]

    assert brief["files_or_symbols"] == []
    assert brief["contract_targets"] == []
    assert brief["blocked_by"] == ["no_safe_source_specific_candidate"]


def test_architect_consumes_advisory_synthesis_as_evidence():
    adr = build_architecture_decision(
        goal="Analyze training project",
        project_report={
            "summary": {"root": "training", "file_count": 2, "languages": ["Python"]},
            "answers": {"1_scope": {"main_task": "Train a model"}, "6_runtime_extraction_readiness": {}},
            "architecture_synthesis_advisory": {
                "artifact_type": "ProjectArchitectureSynthesis",
                "source": "knowledge_backed_architecture_synthesis",
                "architect_consumable": True,
                "recommended_first_slice": {
                    "name": "training_step", "goal": "Bound one update", "target_limit": 1,
                    "targets": ["network.py:backprop"], "steps": ["Verify gradients"],
                },
            },
        },
    )
    assert adr["first_slice_contract"]["targets"] == ["network.py:backprop"]
    assert adr["architecture_synthesis"]["source"] == "knowledge_backed_architecture_synthesis"
