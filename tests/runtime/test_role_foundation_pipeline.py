from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from runtime.role_foundation_pipeline import run_role_foundation_benchmark, run_role_foundation_pipeline


ROOT = Path(__file__).resolve().parents[2]


def test_role_foundation_pipeline_writes_three_artifacts():
    project_dir = ROOT / "benchmarks" / "project_analyzer" / "projects" / "simple_cli_tool"

    result = run_role_foundation_pipeline(
        root=ROOT,
        project_dir=project_dir,
        goal="Prepare ADR and TechnicalSpec",
        write=True,
    )

    assert result["status"] == "ok"
    assert result["kind"] == "role_foundation_pipeline"
    assert result["score"]["passed"] is True
    assert set(result["artifacts"]) == {"project_map_report", "architecture_decision", "technical_spec"}
    assert result["artifacts"]["project_map_report"]["artifact_type"] == "ProjectMapReport"
    assert result["artifacts"]["architecture_decision"]["artifact_type"] == "ArchitectureDecisionRecord"
    assert result["artifacts"]["technical_spec"]["artifact_type"] == "TechnicalSpec"
    assert result["score"]["checks"]["spec_has_source_evidence"] is True
    assert result["score"]["checks"]["spec_has_extraction_contract"] is True
    assert result["score"]["checks"]["spec_contract_candidate_ranked_first"] is True
    assert result["score"]["checks"]["spec_contract_has_selection_reason"] is True
    assert result["score"]["checks"]["spec_acceptance_is_source_linked"] is True
    assert result["safety"]["source_code_changes"] is False
    assert result["safety"]["registry_changes"] is False
    assert result["safety"]["foundry_invoked"] is False
    assert Path(result["report_path"]).exists()
    doc_path = Path(result["human_documents"]["architecture_analysis"])
    assert doc_path.exists()
    doc_text = doc_path.read_text(encoding="utf-8")
    assert "# Architecture Analysis" in doc_text
    assert "## Capability Candidates" in doc_text
    assert "main.py:normalize_text" in doc_text
    for summary in result["artifacts"].values():
        assert Path(summary["path"]).exists()


def test_role_foundation_artifact_paths_do_not_collide():
    project_dir = ROOT / "benchmarks" / "project_analyzer" / "projects" / "simple_cli_tool"

    first = run_role_foundation_pipeline(
        root=ROOT,
        project_dir=project_dir,
        goal="Prepare ADR and TechnicalSpec",
        write=True,
    )
    second = run_role_foundation_pipeline(
        root=ROOT,
        project_dir=project_dir,
        goal="Prepare ADR and TechnicalSpec again",
        write=True,
    )

    assert first["report_path"] != second["report_path"]
    first_paths = {summary["path"] for summary in first["artifacts"].values()}
    second_paths = {summary["path"] for summary in second["artifacts"].values()}
    assert first_paths.isdisjoint(second_paths)


def test_role_foundation_benchmark_single_project():
    report = run_role_foundation_benchmark(
        ROOT,
        benchmarks_dir=ROOT / "benchmarks" / "project_analyzer",
        project="simple_cli_tool",
        write=True,
    )

    assert report["status"] == "ok"
    assert report["project_count"] == 1
    assert report["summary"]["artifact_score"] == 1.0
    assert report["summary"]["candidate_match_score"] == 1.0
    assert report["summary"]["llm_invoked"] == 0
    assert report["cases"][0]["selected_extraction_candidate"] == "main.py:normalize_text"
    assert report["cases"][0]["expected_best_extraction_candidate"] == "main.py:normalize_text"
    assert report["cases"][0]["score"]["checks"]["spec_contract_matches_expected_candidate"] is True
    assert Path(report["report_path"]).exists()


def test_role_foundation_cli_single_project():
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools" / "role_foundation_run.py"),
            "--root",
            str(ROOT),
            "--benchmark",
            "--benchmark-project",
            "simple_cli_tool",
            "--write",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert payload["status"] == "ok"
    assert payload["project_count"] == 1
    assert payload["summary"]["candidate_match_score"] == 1.0
