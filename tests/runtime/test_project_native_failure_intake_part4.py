from __future__ import annotations

from tests.runtime.project_native_failure_intake_helpers import *


def test_fixture_setup_error_cannot_gain_repair_authority_from_test_body(tmp_path):
    project = tmp_path / "library"
    (project / "tests").mkdir(parents=True)
    (project / "src" / "demo").mkdir(parents=True)
    (project / "src" / "demo" / "parser.py").write_text(
        "def parse(value):\n    return value\n", encoding="utf-8"
    )
    (project / "tests" / "test_parser.py").write_text(
        "from demo.parser import parse\n\ndef test_parse(missing_fixture):\n    assert parse('x') == 'x'\n",
        encoding="utf-8",
    )
    output = (
        "ERROR at setup of test_parse\n"
        "fixture 'missing_fixture' not found\n"
        "ERROR tests/test_parser.py::test_parse\n1 error in 0.1s"
    )

    result = _interpret_pytest_result(project, 1, output, {})

    assert result["status"] == "environment_blocked"
    assert result["failure_signature"] is None


def test_declared_pytest_asyncio_plugin_failure_is_environment_blocked(tmp_path):
    project = tmp_path / "async_library"
    project.mkdir()
    (project / "pyproject.toml").write_text(
        "[tool.poetry.group.dev.dependencies]\npytest-asyncio = '^0.23'\n",
        encoding="utf-8",
    )
    output = (
        "FAILED tests/test_async.py::test_parse\n"
        "PytestUnknownMarkWarning: Unknown pytest.mark.asyncio\n"
        "1 failed in 0.1s"
    )

    result = _interpret_pytest_result(project, 1, output, {})

    assert result["status"] == "environment_blocked"
    assert result["failure_signature"] is None
    assert result["environment_reason"] == "declared_pytest_asyncio_plugin_unavailable"


def test_warning_locations_cannot_override_assertion_target(tmp_path):
    project = tmp_path / "invoke"
    source = project / "invoke" / "parser" / "context.py"
    source.parent.mkdir(parents=True)
    source.write_text(
        "class ParserContext:\n"
        "    def help_for(self, name):\n"
        "        return name\n",
        encoding="utf-8",
    )
    (source.parent / "__init__.py").write_text(
        "from .context import ParserContext as Context\n", encoding="utf-8"
    )
    warning_source = project / "invoke" / "watchers.py"
    warning_source.write_text(
        "class Responder:\n"
        "    def __init__(self):\n"
        "        pass\n",
        encoding="utf-8",
    )
    test = project / "cognitive_os_tests" / "test_help.py"
    test.parent.mkdir()
    test.write_text(
        "from invoke.parser import Context\n\n"
        "def test_help():\n"
        "    context = Context()\n"
        "    assert Context.help_for(context, '--intval') == 'INT'\n",
        encoding="utf-8",
    )
    output = (
        "FAILED cognitive_os_tests/test_help.py::test_help\n"
        "E   AssertionError: integer placeholder missing\n"
        "================ warnings summary ================\n"
        "invoke/watchers.py:2: DeprecationWarning: invalid escape sequence\n"
    )

    result = _interpret_pytest_result(project, 1, output, {})

    assert result["production_targets"] == [
        "invoke/parser/context.py:ParserContext.help_for"
    ]
    assert result["target_binding"] == "unique_assertion_causal_call"


def test_cli_help_placeholder_kind_requires_bound_target_and_nodeid():
    target = "invoke/parser/context.py:ParserContext.help_for"
    summary = "AssertionError: integer placeholder missing"
    nodeids = [
        "cognitive_os_tests/test_integer_help_regression.py::"
        "test_integer_defaults_render_int_help_placeholder"
    ]

    assert _failure_kind(target, summary, nodeids) == (
        "cli_help_type_placeholder_contract"
    )
    assert _failure_kind(target, summary, []) is None

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


def test_native_verification_distinguishes_unavailable_regression(tmp_path, monkeypatch):
    project = tmp_path / "demo"
    project.mkdir()
    outcomes = iter([
        {"status": "passed", "exit_code": 0},
        {"status": "environment_blocked", "exit_code": 4},
    ])
    monkeypatch.setattr(
        "runtime.project_native_failure_intake_core._run_pytest",
        lambda *args, **kwargs: next(outcomes),
    )

    result = run_project_native_verification(
        root=tmp_path,
        project=project,
        failing_nodeids=["tests/test_api.py::test_case"],
        policy={"native_failure_intake": {}},
    )

    assert result["status"] == "targeted_passed_regression_environment_blocked"
    assert result["evidence_scope"] == "targeted_only"


def test_legacy_setup_py_selects_distribution_regression_profile(tmp_path):
    project = tmp_path / "historical-checkout"
    project.mkdir()
    (project / "setup.py").write_text(
        "from setuptools import setup\nsetup(name='invoke', version='0.1')\n",
        encoding="utf-8",
    )
    (project / "cognitive_os_tests").mkdir()

    selected = _project_specific_intake(project, {
        "project_regression_targets": {"invoke": ["cognitive_os_tests"]},
    })

    assert selected["regression_targets"] == ["cognitive_os_tests"]
