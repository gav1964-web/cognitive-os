from __future__ import annotations

from pathlib import Path

from runtime.role_foundation_pipeline import _auto_active_root_decision, _requires_scope_selection, run_role_foundation_pipeline


ROOT = Path(__file__).resolve().parents[2]


def test_fixture_only_syntax_damage_does_not_require_scope_selection():
    report = {
        "source_health": {
            "status": "damaged",
            "project_shape": "single_project",
            "inaccessible_count": 0,
            "syntax_error_count": 2,
            "syntax_error_samples": [
                {"path": "testing/data/E12.py", "reason": "SyntaxError"},
                {"path": "docs/jsonrpc-example-code/jsonrpc.py", "reason": "SyntaxError"},
            ],
        }
    }

    assert _requires_scope_selection(report) is False


def test_eval_file_syntax_damage_does_not_require_scope_selection():
    report = {
        "source_health": {
            "status": "damaged",
            "project_shape": "single_project",
            "inaccessible_count": 0,
            "syntax_error_count": 2,
            "syntax_error_samples": [
                {"path": "tests/eval_files/b012_py311.py", "reason": "SyntaxError"},
                {"path": "tests/eval_files/b904_py311.py", "reason": "SyntaxError"},
            ],
        }
    }

    assert _requires_scope_selection(report) is False


def test_test_file_syntax_damage_does_not_require_scope_selection():
    report = {
        "source_health": {
            "status": "damaged",
            "project_shape": "single_project",
            "inaccessible_count": 0,
            "syntax_error_count": 1,
            "syntax_error_samples": [
                {"path": "tests/test_epub_parser.py", "reason": "SyntaxError"},
            ],
        }
    }

    assert _requires_scope_selection(report) is False


def test_role_foundation_blocks_dirty_portfolio_before_adr_and_spec(tmp_path):
    portfolio = tmp_path / "portfolio"
    current = portfolio / "20260101_current"
    legacy = portfolio / "20250101_legacy"
    current.mkdir(parents=True)
    legacy.mkdir(parents=True)
    (current / "requirements.txt").write_text("fastapi==0.115.0\n", encoding="utf-8")
    (current / "main.py").write_text("def normalize(value: str) -> str:\n    return value.strip().lower()\n", encoding="utf-8")
    (legacy / "main.py").write_text("def old_entrypoint(value):\n    return value\n", encoding="utf-8")

    result = run_role_foundation_pipeline(root=ROOT, project_dir=portfolio, goal="Analyze mixed portfolio", write=False)

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

    result = run_role_foundation_pipeline(root=ROOT, project_dir=portfolio, goal="Analyze mixed portfolio", write=True)

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


def test_auto_scope_selects_named_package_despite_test_packaged_copy(tmp_path):
    project = tmp_path / "jupyter-server_jupyter_server"
    package = project / "jupyter_server"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    scope = {
        "candidate_roots": [
            {"path": "jupyter_server", "score": 70, "kind": "python_project_candidate", "python_files": 88},
            {"path": "tests", "score": 18, "kind": "python_project_candidate", "python_files": 86},
        ]
    }

    decision = _auto_active_root_decision(project, scope)

    assert decision["selected_relative_path"] == "jupyter_server"
    assert decision["source"].startswith("auto_")


def test_auto_scope_selects_core_package_when_integrations_are_ambiguous(tmp_path):
    project = tmp_path / "run-llama_llama_index"
    core = project / "llama-index-core"
    core.mkdir(parents=True)
    scope = {
        "candidate_roots": [
            {"path": "llama-index-integrations", "score": 86, "kind": "python_project_candidate", "python_files": 3039},
            {"path": "llama-index-core", "score": 85, "kind": "python_project_candidate", "python_files": 735},
        ]
    }

    decision = _auto_active_root_decision(project, scope)

    assert decision["selected_relative_path"] == "llama-index-core"
    assert decision["source"] == "auto_aliased_core_scope_selector"
