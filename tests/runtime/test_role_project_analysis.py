from pathlib import Path

from runtime.configured_role_pipeline import artifact_by_type, run_configured_role_prefix
from runtime.role_project_analysis import enrich_weak_contract_readiness, prepare_role_project_report


def test_weak_contract_readiness_flattens_list_valued_source_refs():
    report = {
        "answers": {
            "4_contracts_data": {"weak_contract_zones": [["pkg/a.py:parse", "pkg/b.py:validate"]]},
            "6_runtime_extraction_readiness": {"minimal_extraction_plan": {}},
        }
    }

    enriched = enrich_weak_contract_readiness(report)

    rows = enriched["answers"]["6_runtime_extraction_readiness"]["minimal_extraction_plan"]["capabilities_to_extract"]
    assert [row["capability"] for row in rows] == ["pkg/a.py:parse", "pkg/b.py:validate"]


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


def test_project_report_preserves_bounded_reselection_inventory(monkeypatch, tmp_path: Path):
    monkeypatch.setattr("runtime.role_project_analysis.interpret_project_report", lambda *args, **kwargs: {})
    report = {"root": tmp_path.as_posix(), "summary": {}, "answers": {}}

    prepared = prepare_role_project_report(
        root=tmp_path,
        goal="Find a safe fallback",
        analyzer_outputs={
            "project_map_report": report,
            "extract_python_structure": {
                "central_nodes": [{"path": "pkg/features.py", "name": "extract_features"}],
                "pure_transform_candidates": [{"path": "pkg/core.py", "name": "normalize"}],
            },
        },
    )

    assert prepared["reselection_candidate_inventory"] == [
        "pkg/features.py:extract_features",
        "pkg/core.py:normalize",
    ]


def test_project_report_prioritizes_advisory_slice_and_filters_context_only_targets(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(
        "runtime.role_project_analysis.interpret_project_report",
        lambda *args, **kwargs: {
            "architecture_synthesis": {
                "recommended_first_slice": {
                    "targets": ["backup/old.py:format", "pkg/formatters.py:formatMessage"]
                }
            }
        },
    )

    prepared = prepare_role_project_report(
        root=tmp_path,
        goal="Select a record formatter",
        analyzer_outputs={
            "project_map_report": {"root": tmp_path.as_posix(), "summary": {}, "answers": {}},
            "extract_python_structure": {
                "central_nodes": [{"path": "pkg/handlers.py", "name": "emit"}],
            },
        },
    )

    assert prepared["reselection_candidate_inventory"] == [
        "pkg/formatters.py:formatMessage",
        "pkg/handlers.py:emit",
    ]
