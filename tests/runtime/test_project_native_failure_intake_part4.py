from __future__ import annotations

from tests.runtime.project_native_failure_intake_helpers import *

def test_repeated_target_bound_failure_creates_change_request(tmp_path):
    project = tmp_path / "broken_tool"
    project.mkdir()
    _write_project(project, failing=True)
    original = (project / "core.py").read_text(encoding="utf-8")

    report = run_project_native_failure_intake(
        root=tmp_path,
        projects=[project],
        project_stratum="cli_local_tool",
    )

    case = report["cases"][0]
    request = report["qualified_tasks"][0]
    assert report["status"] == "tasks_ready"
    assert case["status"] == "qualified_failure"
    assert request["target"] == "core.py:normalize"
    assert request["authority"] == "failing_contract_test"
    assert request["repeat_count"] == 2
    assert report["policy"]["shard_on_timeout"] is True
    assert report["policy"]["maximum_shards"] == 6
    assert case["source_invariant"]["unchanged"] is True
    assert (project / "core.py").read_text(encoding="utf-8") == original


def test_explicit_test_target_skips_an_unrelated_earlier_failure(tmp_path):
    project = tmp_path / "broken_tool"
    project.mkdir()
    _write_project(project, failing=True)
    (project / "tests" / "test_earlier.py").write_text(
        "def test_unrelated():\n    assert False\n", encoding="utf-8"
    )

    report = run_project_native_failure_intake(
        root=tmp_path,
        projects=[project],
        project_stratum="cli_local_tool",
        test_targets=[r"tests\test_core.py::test_normalize"],
    )

    assert report["status"] == "tasks_ready"
    assert report["policy"]["test_targets"] == ["tests/test_core.py::test_normalize"]
    assert report["cases"][0]["repetitions"][0]["failing_nodeids"] == [
        "tests/test_core.py::test_normalize"
    ]


@pytest.mark.parametrize("target", ["-k expression", "../test_escape.py", "C:/test_abs.py"])
def test_explicit_test_target_rejects_unsafe_paths(tmp_path, target):
    project = tmp_path / "demo"
    project.mkdir()

    with pytest.raises(ValueError, match="unsafe native pytest target"):
        run_project_native_failure_intake(
            root=tmp_path,
            projects=[project],
            project_stratum="cli_local_tool",
            test_targets=[target],
        )


def test_clean_baseline_does_not_create_work(tmp_path):
    project = tmp_path / "clean_library"
    project.mkdir()
    _write_project(project, failing=False)

    report = run_project_native_failure_intake(
        root=tmp_path,
        projects=[project],
        project_stratum="library_pure_transform",
    )

    assert report["status"] == "no_qualified_failure"
    assert report["cases"][0]["status"] == "clean_baseline"
    assert report["qualified_tasks"] == []


def test_collection_dependency_failure_is_not_project_task(tmp_path):
    project = tmp_path / "missing_dependency"
    project.mkdir()
    (project / "tests").mkdir()
    (project / "tests" / "test_import.py").write_text(
        "import package_that_cannot_exist_73491\n",
        encoding="utf-8",
    )

    report = run_project_native_failure_intake(
        root=tmp_path,
        projects=[project],
        project_stratum="cli_local_tool",
    )

    assert report["cases"][0]["status"] == "environment_blocked"
    assert report["qualified_tasks"] == []


def test_native_verification_requires_targeted_and_regression_passes(tmp_path, monkeypatch):
    project = tmp_path / "demo"
    project.mkdir()
    outcomes = iter([
        {"status": "passed", "exit_code": 0},
        {"status": "passed", "exit_code": 0},
    ])
    monkeypatch.setattr(
        "runtime.project_native_failure_intake_core._run_pytest",
        lambda *args, **kwargs: next(outcomes),
    )

    result = run_project_native_verification(
        root=tmp_path,
        project=project,
        failing_nodeids=[r"tests\test_api.py::test_case"],
        policy={"native_failure_intake": {}},
    )

    assert result["status"] == "passed"
    assert result["failing_nodeids"] == ["tests/test_api.py::test_case"]
