from __future__ import annotations

from runtime.role_foundation_pipeline import _auto_active_root_decision


def _candidate(path: str, score: int, python_files: int, *, js_ts_files: int = 0) -> dict[str, object]:
    return {
        "path": path,
        "score": score,
        "kind": "python_project_candidate",
        "python_files": python_files,
        "js_ts_files": js_ts_files,
    }


def test_auto_scope_selects_python_modules_monorepo_root(tmp_path):
    project = tmp_path / "dagster-io__dagster"
    (project / "python_modules").mkdir(parents=True)
    (project / "integration_tests").mkdir()

    decision = _auto_active_root_decision(
        project,
        {
            "candidate_roots": [
                _candidate("python_modules", 85, 115),
                _candidate("integration_tests", 82, 90),
            ]
        },
    )

    assert decision["status"] == "selected"
    assert decision["selected_relative_path"] == "python_modules"
    assert decision["source"] == "auto_monorepo_python_modules_scope_selector"


def test_auto_scope_selects_aliased_core_package_with_noise_penalty(tmp_path):
    project = tmp_path / "localstack__localstack"
    (project / "localstack-core").mkdir(parents=True)
    (project / "tests").mkdir()

    decision = _auto_active_root_decision(
        project,
        {
            "candidate_roots": [
                _candidate("localstack-core", 40, 1198),
                _candidate("tests", 25, 733, js_ts_files=27),
            ]
        },
    )

    assert decision["status"] == "selected"
    assert decision["selected_relative_path"] == "localstack-core"
    assert decision["source"] == "auto_aliased_core_scope_selector"


def test_auto_scope_selects_scientific_library_module_when_best_has_signal_gap(tmp_path):
    project = tmp_path / "scipy__scipy" / "scipy"
    (project / "io").mkdir(parents=True)
    (project / "stats").mkdir()

    decision = _auto_active_root_decision(
        project,
        {"candidate_roots": [_candidate("io", 80, 54), _candidate("stats", 70, 112)]},
    )

    assert decision["status"] == "selected"
    assert decision["selected_relative_path"] == "io"
    assert decision["source"] == "auto_library_module_scope_selector"


def test_auto_scope_keeps_ambiguous_library_modules_blocked_without_gap(tmp_path):
    project = tmp_path / "scipy__scipy" / "scipy"
    (project / "io").mkdir(parents=True)
    (project / "stats").mkdir()

    decision = _auto_active_root_decision(
        project,
        {"candidate_roots": [_candidate("io", 80, 54), _candidate("stats", 78, 112)]},
    )

    assert decision["status"] == "not_selected"


def test_auto_scope_selects_named_package_over_fixture_tests(tmp_path):
    project = tmp_path / "meson-python"
    (project / "tests").mkdir(parents=True)
    (project / "mesonpy").mkdir()
    (project / "mesonpy" / "__init__.py").write_text("", encoding="utf-8")

    decision = _auto_active_root_decision(
        project,
        {
            "candidate_roots": [
                _candidate("tests", 35, 66),
                _candidate("mesonpy", 13, 6),
            ]
        },
    )

    assert decision["status"] == "selected"
    assert decision["selected_relative_path"] == "mesonpy"
    assert decision["source"] == "auto_named_package_over_tests_scope_selector"


def test_auto_scope_selects_github_owner_repo_suffix_package(tmp_path):
    project = tmp_path / "boto_botocore"
    (project / "botocore").mkdir(parents=True)
    (project / "tests").mkdir()

    decision = _auto_active_root_decision(
        project,
        {
            "candidate_roots": [
                _candidate("botocore", 65, 76),
                _candidate("tests", 15, 213),
            ]
        },
    )

    assert decision["status"] == "selected"
    assert decision["selected_relative_path"] == "botocore"
    assert decision["source"].startswith("auto_")


def test_auto_scope_keeps_manifest_backed_main_and_source_package_at_root(tmp_path):
    (tmp_path / "source").mkdir()
    (tmp_path / "source" / "__init__.py").write_text("")
    (tmp_path / "main.py").write_text("def main(): return 0\n")
    (tmp_path / "pyproject.toml").write_text("[project]\nname='downloader'\n")

    decision = _auto_active_root_decision(tmp_path, {"candidate_roots": [_candidate("source", 80, 20)]})

    assert decision["selected_relative_path"] == "."
    assert decision["source"] == "auto_current_python_product_root"


def test_auto_scope_does_not_assume_manifest_backed_script_collection_is_safe(tmp_path):
    for name in ("actions.py", "auth.py", "webhook-bot.py"):
        (tmp_path / name).write_text("def run(): return 0\n")
    (tmp_path / "requirements.txt").write_text("requests\n")

    decision = _auto_active_root_decision(tmp_path, {"candidate_roots": [_candidate("core", 70, 10)]})

    assert decision["selected_relative_path"] is None
    assert decision["source"] != "auto_current_python_product_root"


def test_auto_scope_keeps_manifest_backed_root_package_with_subpackage(tmp_path):
    (tmp_path / "dedupfs").mkdir()
    (tmp_path / "dedupfs" / "__init__.py").write_text("")
    (tmp_path / "__init__.py").write_text("")
    (tmp_path / "service.py").write_text("def run(): return 0\n")
    (tmp_path / "requirements.txt").write_text("telethon\n")

    decision = _auto_active_root_decision(tmp_path, {"candidate_roots": [_candidate("dedupfs", 65, 8)]})

    assert decision["selected_relative_path"] == "."
    assert decision["source"] == "auto_current_python_product_root"
