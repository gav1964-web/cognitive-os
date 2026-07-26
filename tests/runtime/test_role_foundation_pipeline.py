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
    assert result["score"]["checks"]["spec_has_work_plan_contract"] is True
    assert result["score"]["checks"]["spec_contract_candidate_ranked_first"] is True
    assert result["score"]["checks"]["spec_contract_has_selection_reason"] is True
    assert result["score"]["checks"]["spec_acceptance_is_source_linked"] is True
    assert result["score"]["checks"]["architect_red_team_passed"] is True
    assert result["score"]["checks"]["spec_writer_red_team_passed"] is True
    assert result["score"]["checks"]["human_documents_quality_passed"] is True
    assert result["architect_red_team"]["handoff_verdict"] == "ready_for_spec_writer"
    assert result["score"]["human_document_quality"]["status"] == "pass"
    assert result["spec_writer_red_team"]["handoff_verdict"] == "ready_for_implementer"
    assert result["safety"]["source_code_changes"] is False
    assert result["safety"]["registry_changes"] is False
    assert result["safety"]["foundry_invoked"] is False
    assert Path(result["report_path"]).exists()
    doc_path = Path(result["human_documents"]["architecture_analysis"])
    assert doc_path.exists()
    doc_text = doc_path.read_text(encoding="utf-8")
    assert "# Анализ архитектуры" in doc_text
    assert "## Кандидаты в capabilities" in doc_text
    assert "main.py:normalize_text" in doc_text
    spec_doc_path = Path(result["human_documents"]["technical_spec"])
    assert spec_doc_path.exists()
    spec_doc_text = spec_doc_path.read_text(encoding="utf-8")
    assert "# Техническое задание" in spec_doc_text
    assert "## Первый рабочий срез" in spec_doc_text
    assert "## Связанные interface contracts" in spec_doc_text
    assert "## Validation gates и failure modes" in spec_doc_text
    assert "main.py:normalize_text" in spec_doc_text
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


def test_role_foundation_blocks_dirty_portfolio_before_adr_and_spec(tmp_path):
    portfolio = tmp_path / "portfolio"
    current = portfolio / "20260101_current"
    legacy = portfolio / "20250101_legacy"
    current.mkdir(parents=True)
    legacy.mkdir(parents=True)
    (current / "requirements.txt").write_text("fastapi==0.115.0\n", encoding="utf-8")
    (current / "main.py").write_text(
        "def normalize(value: str) -> str:\n"
        "    return value.strip().lower()\n",
        encoding="utf-8",
    )
    (legacy / "main.py").write_text(
        "def old_entrypoint(value):\n"
        "    return value\n",
        encoding="utf-8",
    )

    result = run_role_foundation_pipeline(
        root=ROOT,
        project_dir=portfolio,
        goal="Analyze mixed portfolio",
        write=False,
    )

    assert result["status"] == "blocked"
    assert result["blocker"] == "scope_selection_required"
    assert result["milestone"] == "ProjectMapReport -> ScopeSelectionReport"
    assert set(result["artifacts"]) == {"project_map_report", "scope_selection_report"}
    assert "architecture_decision" not in result["artifacts"]
    assert "technical_spec" not in result["artifacts"]
    assert result["score"]["checks"]["adr_not_built"] is True
    assert result["score"]["checks"]["technical_spec_not_built"] is True
    scope = result["scope_selection_report"]
    assert scope["status"] == "blocked_until_scope_selected"
    assert scope["selection_confidence"] == "ambiguous"
    assert scope["preferred_candidate"] is None
    assert scope["blocked_downstream_artifacts"] == ["ArchitectureDecisionRecord", "TechnicalSpec"]
    assert {row["path"] for row in scope["candidate_roots"]} >= {"20260101_current", "20250101_legacy"}


def test_role_foundation_writes_scope_selection_document_for_dirty_portfolio(tmp_path):
    portfolio = tmp_path / "portfolio"
    current = portfolio / "20260101_current"
    legacy = portfolio / "20250101_legacy"
    current.mkdir(parents=True)
    legacy.mkdir(parents=True)
    (current / "requirements.txt").write_text("fastapi==0.115.0\n", encoding="utf-8")
    (current / "main.py").write_text("def normalize(value: str) -> str:\n    return value.strip()\n", encoding="utf-8")
    (legacy / "main.py").write_text("def old_entrypoint(value):\n    return value\n", encoding="utf-8")

    result = run_role_foundation_pipeline(
        root=ROOT,
        project_dir=portfolio,
        goal="Analyze mixed portfolio",
        write=True,
    )

    assert result["status"] == "blocked"
    doc_path = Path(result["human_documents"]["scope_selection"])
    assert doc_path.exists()
    text = doc_path.read_text(encoding="utf-8")
    assert "# Выбор активного корня проекта" in text
    assert "20260101_current" in text
    assert "ArchitectureDecisionRecord" not in result["artifacts"]
    assert Path(result["report_path"]).exists()


def test_role_foundation_active_root_runs_downstream_on_selected_slice(tmp_path):
    portfolio = tmp_path / "portfolio"
    current = portfolio / "20260101_current"
    legacy = portfolio / "20250101_legacy"
    current.mkdir(parents=True)
    legacy.mkdir(parents=True)
    (current / "requirements.txt").write_text("click==8.3.0\n", encoding="utf-8")
    (current / "main.py").write_text(
        "def normalize(value: str) -> str:\n"
        "    return value.strip().lower()\n\n"
        "def main() -> None:\n"
        "    print(normalize(' A '))\n",
        encoding="utf-8",
    )
    (legacy / "main.py").write_text("def old_entrypoint(value):\n    return value\n", encoding="utf-8")

    result = run_role_foundation_pipeline(
        root=ROOT,
        project_dir=portfolio,
        active_root="20260101_current",
        goal="Analyze selected active root",
        write=False,
    )

    assert result["status"] == "ok"
    assert result["project"].endswith("20260101_current")
    assert result["portfolio_root"].endswith("portfolio")
    assert result["active_root_decision"]["selected_relative_path"] == "20260101_current"
    assert result["artifacts"]["active_root_decision"]["artifact_type"] == "ActiveRootDecision"
    assert result["artifacts"]["architecture_decision"]["artifact_type"] == "ArchitectureDecisionRecord"
    assert result["artifacts"]["technical_spec"]["artifact_type"] == "TechnicalSpec"


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
