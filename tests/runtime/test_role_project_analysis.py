from pathlib import Path

from runtime.configured_role_pipeline import artifact_by_type, run_configured_role_prefix
from runtime.role_project_analysis import prepare_role_project_report


def test_interpreter_synthesis_remains_advisory_to_configured_architect(monkeypatch, tmp_path: Path):
    project = tmp_path / "project"
    (project / "pkg").mkdir(parents=True)
    (project / "pkg" / "ast.py").write_text("def parse(source: str):\n    return source\n", encoding="utf-8")
    project_report = {
        "root": project.as_posix(),
        "summary": {"root": project.as_posix(), "file_count": 1, "entrypoints": [], "languages": ["Python"]},
        "answers": {
            "1_scope": {"domain_profile": {"kind": "generic"}},
            "3_capabilities": {
                "pure_transforms": [
                    {"path": "pkg/ast.py", "name": "parse", "args": [{"name": "source", "annotation": "str"}]}
                ]
            },
            "4_contracts_data": {},
            "6_runtime_extraction_readiness": {
                "minimal_extraction_plan": {
                    "capabilities_to_extract": [{"capability": "pkg/runtime.py:unsafe_runtime"}]
                }
            },
        },
    }
    advisory = {
        "level35_project_signals": {},
        "level4_project_interpretation": {},
        "analysis_tasks": {},
        "architecture_synthesis": {
            "recommended_first_slice": {"targets": ["tests/test_runtime.py:unsafe_runtime"]}
        },
        "knowledge_gap": None,
        "research_plan": None,
    }
    monkeypatch.setattr("runtime.role_project_analysis.interpret_project_report", lambda *args, **kwargs: advisory)

    prepared = prepare_role_project_report(
        root=tmp_path,
        goal="Extract parser",
        analyzer_outputs={"project_map_report": project_report},
    )
    artifacts = run_configured_role_prefix(
        goal="Extract parser",
        project_report=prepared,
        until_artifact_type="TechnicalSpec",
    )

    adr = artifact_by_type(artifacts, "ArchitectureDecisionRecord")
    spec = artifact_by_type(artifacts, "TechnicalSpec")
    assert "architecture_synthesis" not in prepared
    assert prepared["architecture_synthesis_advisory"] == advisory["architecture_synthesis"]
    assert prepared["role_analysis_contract"]["interpretation_authority"] == "advisory_only"
    assert adr["first_slice_contract"]["targets"] == ["pkg/ast.py:parse"]
    assert spec["extraction_contract"]["candidate"] == "pkg/ast.py:parse"
