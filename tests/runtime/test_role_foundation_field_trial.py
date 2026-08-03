from __future__ import annotations

from pathlib import Path

from runtime.role_artifact_quality import evaluate_technical_spec
from runtime.role_foundation_field_trial import _primary_language_scope, _report, _role_scores, discover_python_projects


def test_field_trial_report_uses_project_and_role_minimums():
    report = _report(
        [
            {
                "project": "good",
                "status": "ok",
                "project_min_score": 9.8,
                "role_scores": {"project_analyzer": 10.0, "architect": 9.8, "spec_writer": 9.9},
                "warnings": [],
                "safety": {},
            },
            {
                "project": "weak",
                "status": "ok",
                "project_min_score": 8.4,
                "role_scores": {"project_analyzer": 9.7, "architect": 8.4, "spec_writer": 9.5},
                "warnings": ["architect_red_team_passed"],
                "safety": {},
            },
        ],
        target_score=9.2,
    )

    assert report["status"] == "needs_work"
    assert report["summary"]["project_min_score"] == 8.4
    assert report["summary"]["role_min_scores"]["architect"] == 8.4
    assert report["below_target"][0]["project"] == "weak"


def test_discover_python_projects_uses_projects_child_when_present(tmp_path: Path):
    corpus = tmp_path / "corpus"
    projects = corpus / "projects"
    projects.mkdir(parents=True)
    (projects / "a").mkdir()
    (projects / "a" / "main.py").write_text("print('a')\n", encoding="utf-8")
    (corpus / "not_a_project.py").write_text("print('ignored root file')\n", encoding="utf-8")

    found = discover_python_projects([corpus])

    assert found == [(projects / "a").resolve()]


def test_role_scores_use_semantic_review_floor_for_constrained_spec_handoff():
    scores = _role_scores(
        {
            "score": {"quality": {"results": {"technical_spec": {"score": 98}}}},
            "selected_candidate_quality": {"score": 61, "status": "suspicious"},
            "spec_writer_red_team": {"score": 99},
            "artifacts": {
                "technical_spec": {
                    "extraction_contract": {
                        "semantic_review": {
                            "status": "approved_with_constraints",
                            "checks": {"source_evidence_bound": True, "io_contract_bound": True},
                        }
                    }
                }
            },
            "foundation_semantic_quality": {"role_scores": {"spec_writer": 9.8}},
        }
    )

    assert scores["spec_writer"] == 9.2


def test_role_scores_do_not_score_downstream_roles_for_scope_selection_block():
    scores = _role_scores({"blocker": "scope_selection_required", "score": {"artifact_score": 1.0}})

    assert scores == {"project_analyzer": 10.0, "architect": None, "spec_writer": None}


def test_technical_spec_quality_accepts_constrained_semantic_review_handoff():
    quality = evaluate_technical_spec(
        {
            "requirements": [{"statement": "Extract pyparsing/helpers.py:one_of as a bounded parser-helper contract.", "priority": "must"}],
            "acceptance_criteria": [{"criterion": "Parser helper returns a parser element.", "verification": "Run pytest contract case."}],
            "interface_contracts": [{"source": "pyparsing/helpers.py:one_of", "input_contract": {"strs": "list[str]"}, "output_contract": {"parser": "ParserElement"}}],
            "work_plan_contract": {"obligations": [{"step": "preserve parser-helper behavior"}]},
            "data_lifecycle": [{"stage": "parse"}],
            "error_model": [{"handling": "invalid alternatives return controlled parser error"}],
            "extraction_contract": {
                "candidate": "pyparsing/helpers.py:one_of",
                "ranked_candidates": [{"source": "pyparsing/helpers.py:one_of", "reasons": ["first-slice source evidence"]}],
                "input_contract": {"strs": "list[str]"},
                "output_contract": {"parser": "ParserElement"},
                "semantic_quality": {"status": "suspicious", "score": 61},
                "semantic_review": {"status": "approved_with_constraints", "checks": {"source_evidence_bound": True}},
                "side_effects": {"declared": []},
            },
            "source_evidence": [{"source": "pyparsing/helpers.py:one_of"}, {"source": "pyparsing/helpers.py:ParserElement"}],
            "traceability_table": [{"source": "pyparsing/helpers.py:one_of", "acceptance_id": "AC-1"}],
            "implementation_handoff": {"patch_scope": ["pyparsing/helpers.py:one_of"]},
            "engineering_quality_gate": {"verification_commands": ["python -m pytest tests"]},
            "human_review": {"open_questions": [], "non_goals": ["No parser rewrite."]},
            "non_goals": ["No parser rewrite."],
        }
    )

    assert "selected_candidate_quality_is_usable" not in quality["warnings"]


def test_discover_python_projects_keeps_manifest_root_as_one_project(tmp_path: Path):
    project = tmp_path / "orjson_like"
    (project / "test").mkdir(parents=True)
    (project / "pyproject.toml").write_text("[project]\nname='orjson-like'\n", encoding="utf-8")
    (project / "test" / "test_default.py").write_text("def test_default():\n    pass\n", encoding="utf-8")

    found = discover_python_projects([project])

    assert found == [project.resolve()]


def test_primary_language_scope_marks_rust_workspace_with_python_assets_out_of_scope(tmp_path: Path):
    project = tmp_path / "mixed"
    (project / "crates" / "dbt-core" / "src").mkdir(parents=True)
    (project / "crates" / "templates").mkdir(parents=True)
    (project / "Cargo.toml").write_text("[workspace]\nmembers=[]\n", encoding="utf-8")
    for index in range(24):
        (project / "crates" / "dbt-core" / "src" / f"lib{index}.rs").write_text("fn main() {}\n", encoding="utf-8")
    (project / "crates" / "templates" / "helper.py").write_text("print('template')\n", encoding="utf-8")
    (project / "crates" / "templates" / "test_helper.py").write_text("def test_helper(): pass\n", encoding="utf-8")

    scope = _primary_language_scope(project)

    assert scope["status"] == "out_of_scope"
    assert scope["reason_code"] == "unsupported_primary_language_for_python_foundation"


def test_primary_language_scope_keeps_python_package_in_scope(tmp_path: Path):
    project = tmp_path / "pkg"
    (project / "pkg").mkdir(parents=True)
    (project / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (project / "pkg" / "core.py").write_text("def normalize(value): return value\n", encoding="utf-8")
    (project / "pyproject.toml").write_text("[project]\nname='pkg'\n", encoding="utf-8")

    assert _primary_language_scope(project)["status"] == "in_scope"
