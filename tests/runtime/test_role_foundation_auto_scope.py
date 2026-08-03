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
