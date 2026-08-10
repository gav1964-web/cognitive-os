from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from runtime.role_foundation_pipeline import _auto_active_root_decision, _enrich_weak_contract_readiness
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


def test_auto_scope_selects_repo_named_package_with_high_confidence(tmp_path):
    project = tmp_path / "owner__engine"
    (project / "engine").mkdir(parents=True)
    (project / "web").mkdir()
    scope_report = {
        "candidate_roots": [
            {"path": "engine", "score": 77, "kind": "python_project_candidate"},
            {"path": "web", "score": 70, "kind": "mixed_python_frontend_candidate"},
        ]
    }

    decision = _auto_active_root_decision(project, scope_report)

    assert decision["status"] == "selected"
    assert decision["selected_relative_path"] == "engine"
    assert decision["source"] == "auto_safe_scope_selector"


def test_auto_scope_selects_high_score_repo_named_package_on_tie(tmp_path):
    project = tmp_path / "plotly__dash"
    (project / "dash").mkdir(parents=True)
    (project / "components").mkdir()
    scope_report = {
        "candidate_roots": [
            {"path": "dash", "score": 110, "kind": "mixed_python_frontend_candidate"},
            {"path": "components", "score": 110, "kind": "mixed_python_frontend_candidate"},
        ]
    }

    decision = _auto_active_root_decision(project, scope_report)

    assert decision["status"] == "selected"
    assert decision["selected_relative_path"] == "dash"
    assert decision["score_gap_to_next"] == 0


def test_auto_scope_selects_native_python_package_over_examples(tmp_path):
    project = tmp_path / "PyO3__setuptools-rust"
    package = project / "setuptools_rust"
    examples = project / "examples"
    package.mkdir(parents=True)
    examples.mkdir()
    (project / "pyproject.toml").write_text("[project]\nname='setuptools-rust'\n", encoding="utf-8")
    (package / "__init__.py").write_text("", encoding="utf-8")
    scope_report = {
        "candidate_roots": [
            {"path": "examples", "score": 80, "kind": "python_project_candidate"},
            {"path": "setuptools_rust", "score": 20, "kind": "python_project_candidate"},
        ]
    }

    decision = _auto_active_root_decision(project, scope_report)

    assert decision["status"] == "selected"
    assert decision["selected_relative_path"] == "setuptools_rust"


def test_auto_scope_selects_python_facing_package_in_frontend_monorepo(tmp_path):
    project = tmp_path / "jupyterlab__jupyterlab"
    (project / "packages").mkdir(parents=True)
    (project / "jupyterlab").mkdir()
    scope_report = {
        "candidate_roots": [
            {"path": "packages", "score": 112, "kind": "mixed_python_frontend_candidate", "python_files": 6},
            {"path": "jupyterlab", "score": 104, "kind": "mixed_python_frontend_candidate", "python_files": 44},
            {"path": "galata", "score": 80, "kind": "frontend_or_extension_candidate", "python_files": 0},
        ]
    }

    decision = _auto_active_root_decision(project, scope_report)

    assert decision["status"] == "selected"
    assert decision["selected_relative_path"] == "jupyterlab"
    assert decision["source"] == "auto_python_facing_scope_selector"


def test_auto_scope_selects_application_package_over_tooling_package(tmp_path):
    project = tmp_path / "home-assistant__core"
    (project / "pylint").mkdir(parents=True)
    (project / "homeassistant").mkdir()
    scope_report = {
        "candidate_roots": [
            {"path": "pylint", "score": 60, "kind": "python_project_candidate", "python_files": 66},
            {"path": "homeassistant", "score": 50, "kind": "python_project_candidate", "python_files": 9849},
            {"path": "tests", "score": 21, "kind": "python_project_candidate", "python_files": 8067},
        ]
    }

    decision = _auto_active_root_decision(project, scope_report)

    assert decision["status"] == "selected"
    assert decision["selected_relative_path"] == "homeassistant"
    assert decision["source"] == "auto_application_package_scope_selector"


def test_role_foundation_enriches_weak_contract_readiness():
    report = _enrich_weak_contract_readiness(
        {
            "answers": {
                "4_contracts_data": {"weak_contract_zones": ["src/zope/testing/doctestcase.py:_run_test"]},
                "6_runtime_extraction_readiness": {
                    "contract_test_strategy": {"hand_written_negative_tests": ""},
                    "data_lifecycle": [{"stage": "unknown"}],
                    "minimal_extraction_plan": {"blocked_by": "no_safe_python_candidate"},
                },
            }
        }
    )
    readiness = report["answers"]["6_runtime_extraction_readiness"]

    assert readiness["minimal_extraction_plan"]["capabilities_to_extract"][0]["capability"].endswith(":_run_test")
    assert "blocked_by" not in readiness["minimal_extraction_plan"]
    assert len(readiness["data_lifecycle"]) == 3


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


def test_role_foundation_auto_selects_clear_named_package_root(tmp_path):
    project = tmp_path / "sample_tool"
    package = project / "sample_tool"
    tests = project / "tests"
    package.mkdir(parents=True)
    tests.mkdir()
    (project / "pyproject.toml").write_text("[project]\nname='sample-tool'\n", encoding="utf-8")
    for index in range(18):
        (package / f"mod_{index}.py").write_text(
            f"def normalize_{index}(value: str) -> str:\n"
            "    return value.strip().lower()\n",
            encoding="utf-8",
        )
    for index in range(4):
        (tests / f"test_{index}.py").write_text("def test_placeholder():\n    assert True\n", encoding="utf-8")
    (tests / "broken_fixture.py").write_text("def invalid(:\n    pass\n", encoding="utf-8")

    result = run_role_foundation_pipeline(
        root=ROOT,
        project_dir=project,
        goal="Analyze obvious package root",
        write=False,
    )

    assert result["status"] == "ok"
    assert result["active_root_decision"]["source"] == "auto_safe_scope_selector"
    assert result["active_root_decision"]["selected_relative_path"] == "sample_tool"


def test_role_foundation_active_root_tolerates_newer_python_syntax(tmp_path):
    project = tmp_path / "modernpkg"
    package = project / "modernpkg"
    package.mkdir(parents=True)
    (project / "pyproject.toml").write_text("[project]\nname='modernpkg'\n", encoding="utf-8")
    (package / "core.py").write_text(
        "type Alias = str\n\n"
        "def parse_value[T](value: T) -> T:\n"
        "    return value\n",
        encoding="utf-8",
    )
    (package / "fallback.py").write_text(
        "def normalize(value: str) -> str:\n"
        "    return value.strip().lower()\n",
        encoding="utf-8",
    )

    result = run_role_foundation_pipeline(
        root=ROOT,
        project_dir=project,
        goal="Analyze modern Python package",
        write=False,
    )

    assert result["status"] == "ok"
    assert result["active_root_decision"]["selected_relative_path"] == "modernpkg"


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
