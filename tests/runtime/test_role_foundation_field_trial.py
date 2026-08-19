from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from runtime.role_artifact_quality import evaluate_technical_spec
from runtime.role_foundation_field_trial import _apply_role_score_caps, _case_status, _primary_language_scope, _report, _role_scores, discover_python_projects


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


def test_field_trial_report_calibrates_single_clean_corpus_below_promotion_claim():
    cases = [
        {
            "project": f"clean_{index}",
            "status": "ok",
            "project_min_score": 10.0,
            "role_scores": {"project_analyzer": 10.0, "architect": 10.0, "spec_writer": 10.0},
            "warnings": [],
            "safety": {},
        }
        for index in range(39)
    ]

    report = _report(cases, target_score=9.7)

    assert report["status"] == "ok"
    assert report["promotion_status"] == "needs_more_evidence"
    assert report["summary"]["readiness_min_score"] == 10.0
    assert report["calibration"]["calibrated_readiness_min_score"] == 9.0
    assert report["calibration"]["target_met"] is False


def test_field_trial_report_allows_very_wide_clean_corpus_to_claim_promotion_target():
    cases = [
        {
            "project": f"clean_{index}",
            "status": "ok",
            "project_min_score": 9.8,
            "role_scores": {"project_analyzer": 9.8, "architect": 9.8, "spec_writer": 9.8},
            "warnings": [],
            "safety": {},
        }
        for index in range(320)
    ]

    report = _report(cases, target_score=9.7)

    assert report["status"] == "ok"
    assert report["promotion_status"] == "ready_for_9_7"
    assert report["calibration"]["calibrated_readiness_min_score"] == 9.7
    assert report["calibration"]["evidence_tier"] == "promotion_candidate"


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

    assert scores == {"project_analyzer": 9.7, "architect": None, "spec_writer": None}


def test_role_scores_do_not_score_downstream_roles_without_safe_python_candidate():
    scores = _role_scores({"blocker": "no_safe_python_candidate", "score": {"artifact_score": 0.94}})

    assert scores == {"project_analyzer": 9.4, "architect": None, "spec_writer": None}


def test_published_role_scores_apply_conservative_caps():
    assert _apply_role_score_caps(
        {"project_analyzer": 10.0, "architect": 10.0, "spec_writer": 10.0}
    ) == {"project_analyzer": 9.7, "architect": 9.7, "spec_writer": 9.8}


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


def test_discovery_keeps_cloned_non_python_repo_for_scope_reporting(tmp_path: Path):
    corpus = tmp_path / "corpus"
    python_repo = corpus / "owner__python"
    non_python_repo = corpus / "owner__other"
    for repo in (python_repo, non_python_repo):
        (repo / ".git").mkdir(parents=True)
    (python_repo / "app.py").write_text("print('ok')\n", encoding="utf-8")
    (non_python_repo / "main.js").write_text("console.log('ok')\n", encoding="utf-8")

    found = discover_python_projects([corpus])

    assert found == [non_python_repo.resolve(), python_repo.resolve()]


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
    assert scope["primary_language"] == "Rust native extension"
    assert scope["reason_code"] == "unsupported_primary_language_for_python_foundation"


def test_primary_language_scope_marks_native_core_without_python_impl_out_of_scope(tmp_path: Path):
    project = tmp_path / "ijl__orjson"
    (project / "pysrc" / "orjson").mkdir(parents=True)
    (project / "bench").mkdir()
    (project / "test").mkdir()
    (project / "src").mkdir()
    (project / "Cargo.toml").write_text("[package]\nname='orjson'\n", encoding="utf-8")
    (project / "pyproject.toml").write_text("[project]\nname='orjson'\n", encoding="utf-8")
    (project / "pysrc" / "orjson" / "__init__.py").write_text("from .orjson import dumps\n", encoding="utf-8")
    (project / "bench" / "__init__.py").write_text("", encoding="utf-8")
    (project / "bench" / "benchmark.py").write_text("def helper(): pass\n", encoding="utf-8")
    (project / "test" / "test_api.py").write_text("def test_api(): pass\n", encoding="utf-8")
    for index in range(24):
        (project / "src" / f"lib{index}.rs").write_text("fn dumps() {}\n", encoding="utf-8")

    scope = _primary_language_scope(project)

    assert scope["status"] == "out_of_scope"
    assert scope["python_source_files"] == 1
    assert scope["reason_code"] == "unsupported_primary_language_for_python_foundation"


def test_primary_language_scope_marks_c_runtime_core_out_of_scope(tmp_path: Path):
    project = tmp_path / "cpython_like"
    for dirname in ("Include", "Modules", "Objects", "Python", "Lib"):
        (project / dirname).mkdir(parents=True)
    (project / "pyproject.toml").write_text("[project]\nname='cpython-like'\n", encoding="utf-8")
    for index in range(40):
        (project / "Lib" / f"module{index}.py").write_text("def helper(): pass\n", encoding="utf-8")
    for index in range(60):
        (project / "Modules" / f"module{index}.c").write_text("int main(void) { return 0; }\n", encoding="utf-8")
        (project / "Include" / f"header{index}.h").write_text("#pragma once\n", encoding="utf-8")

    scope = _primary_language_scope(project)

    assert scope["status"] == "out_of_scope"
    assert scope["primary_language"] == "C"
    assert scope["reason_code"] == "unsupported_primary_language_for_python_foundation"


def test_primary_language_scope_marks_cpp_runtime_core_out_of_scope(tmp_path: Path):
    project = tmp_path / "greenlet_like"
    (project / "src" / "greenlet").mkdir(parents=True)
    (project / "pyproject.toml").write_text("[project]\nname='greenlet-like'\n", encoding="utf-8")
    (project / "src" / "greenlet" / "__init__.py").write_text("from ._greenlet import greenlet\n", encoding="utf-8")
    for index in range(12):
        (project / "src" / f"core{index}.cpp").write_text("int main(void) { return 0; }\n", encoding="utf-8")
        (project / "src" / f"core{index}.hpp").write_text("#pragma once\n", encoding="utf-8")

    scope = _primary_language_scope(project)

    assert scope["status"] == "out_of_scope"
    assert scope["primary_language"] == "C++"
    assert scope["reason_code"] == "unsupported_primary_language_for_python_foundation"


def test_primary_language_scope_marks_type_stub_corpus_out_of_scope(tmp_path: Path):
    project = tmp_path / "typeshed_like"
    (project / "stdlib").mkdir(parents=True)
    (project / "stubs" / "demo").mkdir(parents=True)
    (project / "lib" / "tools").mkdir(parents=True)
    for index in range(210):
        target = project / ("stdlib" if index % 2 else "stubs/demo") / f"mod_{index}.pyi"
        target.write_text("def value() -> str: ...\n", encoding="utf-8")
    for index in range(5):
        (project / "lib" / "tools" / f"tool_{index}.py").write_text("def run():\n    return None\n", encoding="utf-8")

    scope = _primary_language_scope(project)

    assert scope["status"] == "out_of_scope"
    assert scope["reason_code"] == "unsupported_type_stub_corpus_for_python_foundation"


def test_primary_language_scope_marks_native_extension_wrapper_out_of_scope(tmp_path: Path):
    project = tmp_path / "bcrypt_like"
    (project / "src" / "pkg").mkdir(parents=True)
    (project / "src" / "_pkg" / "src").mkdir(parents=True)
    (project / "src" / "pkg" / "__init__.py").write_text("from ._pkg import hashpw\n", encoding="utf-8")
    (project / "src" / "_pkg" / "src" / "lib.rs").write_text("pub fn hashpw() {}\n", encoding="utf-8")
    (project / "release.py").write_text("def release(version):\n    return None\n", encoding="utf-8")
    (project / "pyproject.toml").write_text("[project]\nname='pkg'\n", encoding="utf-8")

    scope = _primary_language_scope(project)

    assert scope["status"] == "out_of_scope"
    assert scope["primary_language"] == "Rust native extension"


def test_primary_language_scope_marks_cpp_extension_wrapper_out_of_scope(tmp_path: Path):
    project = tmp_path / "rapidjson_like"
    project.mkdir()
    (project / "setup.py").write_text("from setuptools import setup\n", encoding="utf-8")
    (project / "rapidjson.cpp").write_text("int main(void) { return 0; }\n", encoding="utf-8")
    (project / "release.py").write_text("version = '0.0.0'\n", encoding="utf-8")
    (project / "tests").mkdir()
    (project / "tests" / "test_api.py").write_text("def test_api(): pass\n", encoding="utf-8")

    scope = _primary_language_scope(project)

    assert scope["status"] == "out_of_scope"
    assert scope["primary_language"] == "C++ native extension"


def test_primary_language_scope_marks_examples_only_repo_out_of_scope(tmp_path: Path):
    project = tmp_path / "examples-only"
    (project / "examples" / "python").mkdir(parents=True)
    (project / "examples" / "python" / "main.py").write_text("print('example')\n", encoding="utf-8")

    scope = _primary_language_scope(project)

    assert scope["status"] == "out_of_scope"
    assert scope["reason_code"] == "no_python_owned_product_boundary"


def test_primary_language_scope_marks_setup_docs_and_tests_only_repo_out_of_scope(tmp_path: Path):
    project = tmp_path / "support-only"
    (project / "docs").mkdir(parents=True)
    (project / "test").mkdir()
    (project / "setup.py").write_text("from setuptools import setup\n", encoding="utf-8")
    (project / "docs" / "conf.py").write_text("project = 'sample'\n", encoding="utf-8")
    (project / "test" / "test_api.py").write_text("def test_api(): pass\n", encoding="utf-8")

    scope = _primary_language_scope(project)

    assert scope["status"] == "out_of_scope"
    assert scope["reason_code"] == "no_python_owned_product_boundary"


def test_primary_language_scope_marks_docs_tools_and_temporary_scripts_out_of_scope(tmp_path: Path):
    project = tmp_path / "docs-tools"
    (project / "_pages").mkdir(parents=True)
    (project / "tools").mkdir()
    (project / "scripts").mkdir()
    (project / "_pages" / "conf.py").write_text("project = 'docs'\n", encoding="utf-8")
    (project / "tools" / "lint.py").write_text("print('lint')\n", encoding="utf-8")
    (project / "scripts" / "pytmp.py").write_text("print('temporary')\n", encoding="utf-8")

    assert _primary_language_scope(project)["status"] == "out_of_scope"


def test_primary_language_scope_marks_single_notebook_export_out_of_scope(tmp_path: Path):
    project = tmp_path / "guide"
    project.mkdir()
    (project / "Getting Started.py").write_text("print('notebook export')\n", encoding="utf-8")

    assert _primary_language_scope(project)["status"] == "out_of_scope"


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
