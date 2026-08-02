from __future__ import annotations

from pathlib import Path

from runtime.role_foundation_field_trial import _primary_language_scope, _report, discover_python_projects


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
