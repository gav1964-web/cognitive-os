from __future__ import annotations

from runtime.architecture_decision_builder import build_architecture_decision


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
