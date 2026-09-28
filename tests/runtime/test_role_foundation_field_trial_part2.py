from __future__ import annotations

from tests.runtime.role_foundation_field_trial_helpers import *

def test_primary_language_scope_marks_repo_without_python_out_of_scope(tmp_path: Path):
    project = tmp_path / "javascript"
    project.mkdir()
    (project / "main.js").write_text("console.log('ok')\n", encoding="utf-8")

    scope = _primary_language_scope(project)

    assert scope["status"] == "out_of_scope"
    assert scope["reason_code"] == "no_python_owned_product_boundary"


def test_primary_language_scope_keeps_python_package_in_scope(tmp_path: Path):
    project = tmp_path / "pkg"
    (project / "pkg").mkdir(parents=True)
    (project / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (project / "pkg" / "core.py").write_text("def normalize(value): return value\n", encoding="utf-8")
    (project / "pyproject.toml").write_text("[project]\nname='pkg'\n", encoding="utf-8")

    assert _primary_language_scope(project)["status"] == "in_scope"


def test_primary_language_scope_tolerates_inaccessible_subtree(tmp_path: Path):
    project = tmp_path / "pkg"
    (project / "pkg").mkdir(parents=True)
    (project / "broken").mkdir()
    (project / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    real_walk = __import__("os").walk

    def noisy_walk(path, *args, **kwargs):
        for current, dirs, files in real_walk(path, *args, **kwargs):
            if Path(current).name == "broken":
                onerror = kwargs.get("onerror")
                if onerror:
                    onerror(OSError("broken subtree"))
                continue
            yield current, dirs, files

    with patch("runtime._parts.role_foundation_field_trial_scope.os.walk", side_effect=noisy_walk):
        scope = _primary_language_scope(project)

    assert scope["status"] == "in_scope"


def test_field_trial_exact_projects_bypass_corpus_discovery(tmp_path: Path):
    first = tmp_path / "z_portfolio"
    second = tmp_path / "a_portfolio"
    first.mkdir()
    second.mkdir()

    def bounded(_runner, kwargs, _timeout):
        return {"project": kwargs["project_dir"].name}

    with (
        patch("runtime.role_foundation_field_trial.discover_python_projects") as discover,
        patch("runtime.role_foundation_field_trial.run_bounded_foundation_case", side_effect=bounded),
        patch("runtime.role_foundation_field_trial._report", side_effect=lambda cases, **_: {"status": "ok", "cases": cases}),
    ):
        report = run_role_foundation_field_trial(
            root=tmp_path,
            project_roots=[],
            exact_project_roots=[first, second],
            limit=1,
        )

    discover.assert_not_called()
    assert [case["project"] for case in report["cases"]] == ["a_portfolio"]


def test_versioned_python_portfolio_is_admitted_to_scope_selection(tmp_path: Path):
    portfolio = tmp_path / "portfolio"
    current = portfolio / "202608_current"
    legacy = portfolio / "202401_legacy"
    current.mkdir(parents=True)
    legacy.mkdir()
    (current / "requirements.txt").write_text("fastapi==0.115.0\n", encoding="utf-8")
    (current / "main.py").write_text("def run(): return 1\n", encoding="utf-8")
    (legacy / "main.py").write_text("def run(): return 0\n", encoding="utf-8")

    assert _primary_language_scope(portfolio)["status"] == "out_of_scope"
    assert _is_workspace_portfolio_candidate(portfolio) is True
