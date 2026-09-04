from __future__ import annotations

from tests.runtime.project_native_failure_intake_helpers import *

def test_local_install_uses_offline_non_editable_fallback(tmp_path, monkeypatch):
    project = tmp_path / "demo"
    project.mkdir()
    (project / "setup.py").write_text("from setuptools import setup; setup()\n", encoding="utf-8")
    calls = []
    outcomes = iter([
        SimpleNamespace(returncode=1, stdout="editable failed", stderr=""),
        SimpleNamespace(returncode=0, stdout="wheel installed", stderr=""),
    ])
    monkeypatch.setattr("runtime.project_native_failure_intake.venv.EnvBuilder.create", lambda self, path: None)

    def fake_run(command, **kwargs):
        calls.append(command)
        return next(outcomes)

    monkeypatch.setattr("runtime.project_native_failure_environment._run_bounded_process", fake_run)

    _, preparation = _prepare_local_project(project, {"local_editable_install": True})

    assert preparation["status"] == "ready"
    assert preparation["reason"] == "local_non_editable_install_ready"
    assert "-e" in calls[0]
    assert "-e" not in calls[1]
    assert "--no-deps" in calls[1]


def test_relative_pytest_basetemp_is_moved_outside_project(tmp_path):
    project = tmp_path / "copy" / "p"
    project.mkdir(parents=True)

    arguments = _pytest_arguments(
        project,
        {"pytest_arguments": ["-q", "--basetemp=.pytest-native-intake"]},
    )

    assert arguments[0] == "-q"
    basetemp = Path(arguments[1].split("=", 1)[1])
    assert basetemp == (project.parent / ".pytest-native-intake").resolve()
    assert project not in basetemp.parents


def test_absolute_pytest_basetemp_is_preserved(tmp_path):
    project = tmp_path / "copy" / "p"
    project.mkdir(parents=True)
    configured = (tmp_path / "native-temp").resolve()

    arguments = _pytest_arguments(
        project,
        {"pytest_arguments": ["--basetemp", str(configured)]},
    )

    assert arguments == ["--basetemp", str(configured)]


def test_relative_pytest_basetemp_uses_configured_short_root(tmp_path):
    project = tmp_path / "long" / "execution" / "patch_sandbox" / "project"
    project.mkdir(parents=True)
    short_root = tmp_path / ".nft"

    arguments = _pytest_arguments(project, {
        "pytest_arguments": ["--basetemp=.pytest-native-intake"],
        "short_basetemp_path": str(short_root),
    })

    basetemp = Path(arguments[0].split("=", 1)[1])
    assert basetemp.parent == short_root.resolve()
    assert len(basetemp.name) == 12


def test_project_dependency_overlay_follows_distribution_identity(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "setup.cfg").write_text("[metadata]\nname = flake8\n", encoding="utf-8")

    selected = _project_specific_intake(project, {
        "dependency_overlay_path": "global",
        "project_dependency_overlay_paths": {"flake8": "bounded/flake8"},
    })

    assert selected["dependency_overlay_path"] == "bounded/flake8"
    assert selected["dependency_overlay_identity"] == "flake8"
    assert selected["tool_overlay_path"] == "global"


def test_project_dependency_overlay_reads_pyproject_distribution_identity(tmp_path):
    project = tmp_path / "checkout-name"
    project.mkdir()
    (project / "pyproject.toml").write_text(
        "[project]\nname = 'isort'\n", encoding="utf-8"
    )

    selected = _project_specific_intake(project, {
        "dependency_overlay_path": "global",
        "project_dependency_overlay_paths": {"isort": "bounded/isort"},
    })

    assert selected["dependency_overlay_path"] == "bounded/isort"
    assert selected["dependency_overlay_identity"] == "isort"
    assert selected["tool_overlay_path"] == "global"


def test_project_pytest_plugins_are_explicitly_allowlisted_by_distribution(tmp_path):
    project = tmp_path / "checkout"
    project.mkdir()
    (project / "pyproject.toml").write_text("[project]\nname = 'isort'\n", encoding="utf-8")

    selected = _project_specific_intake(project, {
        "pytest_arguments": ["-q"],
        "project_pytest_plugins": {
            "isort": ["pytest_benchmark.plugin", "invalid-plugin"],
        },
    })

    assert selected["pytest_arguments"] == ["-q", "-p", "pytest_benchmark.plugin"]
    assert selected["explicit_pytest_plugins"] == ["pytest_benchmark.plugin"]


def test_nested_pytest_plugins_are_explicitly_allowlisted_by_distribution(tmp_path):
    project = tmp_path / "checkout"
    project.mkdir()
    (project / "pyproject.toml").write_text(
        "[project]\nname = 'pytest-randomly'\n", encoding="utf-8"
    )

    selected = _project_specific_intake(project, {
        "project_nested_pytest_plugins": {
            "pytest-randomly": ["faker.contrib.pytest.plugin", "bad-plugin"],
        },
    })

    assert selected["nested_pytest_plugins"] == ["faker.contrib.pytest.plugin"]


def test_project_pytest_arguments_are_scoped_by_distribution(tmp_path):
    project = tmp_path / "checkout"
    project.mkdir()
    (project / "pyproject.toml").write_text("[project]\nname = 'isort'\n", encoding="utf-8")

    selected = _project_specific_intake(project, {
        "pytest_arguments": ["-q"],
        "project_pytest_arguments": {
            "isort": ["--ignore=tests/integration/test_projects_using_isort.py"],
        },
    })

    assert selected["pytest_arguments"] == [
        "-q", "--ignore=tests/integration/test_projects_using_isort.py"
    ]
    assert selected["project_pytest_arguments_applied"] == [
        "--ignore=tests/integration/test_projects_using_isort.py"
    ]


def test_project_probe_settings_are_allowlisted_by_distribution(tmp_path):
    project = tmp_path / "checkout"
    project.mkdir()
    (project / "pyproject.toml").write_text("[project]\nname = 'pluggy'\n", encoding="utf-8")

    selected = _project_specific_intake(project, {
        "local_editable_install": True,
        "probe_path_bootstrap": True,
        "project_probe_settings": {
            "pluggy": {
                "local_editable_install": False,
                "probe_path_bootstrap": False,
                "timeout_seconds": 999,
            },
        },
    })

    assert selected["local_editable_install"] is False
    assert selected["probe_path_bootstrap"] is False
    assert selected["project_probe_settings_applied"] == {
        "local_editable_install": False,
        "probe_path_bootstrap": False,
    }
    assert "timeout_seconds" not in selected["project_probe_settings_applied"]


def test_assertion_causal_analysis_ignores_nested_scope_assignment_shadow(tmp_path):
    source = tmp_path / "src" / "demo" / "engine.py"
    source.parent.mkdir(parents=True)
    source.write_text(
        "class Engine:\n"
        "    def execute(self):\n"
        "        return 'actual'\n",
        encoding="utf-8",
    )
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_engine.py").write_text(
        "from demo.engine import Engine\n\n"
        "def test_execute():\n"
        "    def nested():\n"
        "        result = 'shadow'\n"
        "        return result\n"
        "    result = Engine.execute(Engine())\n"
        "    assert result == 'expected'\n",
        encoding="utf-8",
    )

    analysis = _test_assertion_causal_analysis(
        tmp_path, ["tests/test_engine.py::test_execute"]
    )

    assert analysis["production_targets"] == ["src/demo/engine.py:Engine.execute"]


def test_assertion_causal_analysis_binds_unique_prior_state_transition(tmp_path):
    source = tmp_path / "src" / "demo" / "server.py"
    source.parent.mkdir(parents=True)
    source.write_text(
        "class HTTPServer:\n"
        "    def start(self):\n"
        "        self.running = True\n"
        "    def is_running(self):\n"
        "        return self.running\n",
        encoding="utf-8",
    )
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_server.py").write_text(
        "from demo.server import HTTPServer\n\n"
        "class FailingServer(HTTPServer):\n"
        "    def wait(self):\n"
        "        raise RuntimeError\n\n"
        "def test_start_failure_stops_server():\n"
        "    server = FailingServer()\n"
        "    server.start()\n"
        "    assert not server.is_running()\n",
        encoding="utf-8",
    )

    analysis = _test_assertion_causal_analysis(
        tmp_path, ["tests/test_server.py::test_start_failure_stops_server"]
    )

    assert analysis["production_targets"] == ["src/demo/server.py:HTTPServer.start"]


def test_assertion_causal_analysis_rejects_ambiguous_state_transitions(tmp_path):
    source = tmp_path / "src" / "demo" / "server.py"
    source.parent.mkdir(parents=True)
    source.write_text(
        "class HTTPServer:\n"
        "    def start(self):\n        pass\n"
        "    def clear(self):\n        pass\n"
        "    def is_running(self):\n        return True\n",
        encoding="utf-8",
    )
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_server.py").write_text(
        "from demo.server import HTTPServer\n\n"
        "class LocalServer(HTTPServer):\n    pass\n\n"
        "def test_state():\n"
        "    server = LocalServer()\n"
        "    server.start()\n"
        "    server.clear()\n"
        "    assert not server.is_running()\n",
        encoding="utf-8",
    )

    analysis = _test_assertion_causal_analysis(
        tmp_path, ["tests/test_server.py::test_state"]
    )

    assert analysis["production_targets"] == []
    assert analysis["reason"] == "no_project_production_target_in_assertion_slice"


def test_production_targets_canonicalize_absolute_windows_traceback_path(tmp_path):
    source = tmp_path / "isort" / "parse.py"
    source.parent.mkdir()
    source.write_text(
        "def file_contents():\n    raise IndexError('out of range')\n", encoding="utf-8"
    )
    traceback_path = str(source)

    targets = _production_targets(tmp_path, f"{traceback_path}:2: in file_contents\n")

    assert targets == ["isort/parse.py:file_contents"]


def test_production_targets_rebind_nested_pytest_sandbox_path(tmp_path):
    source = tmp_path / "src" / "demo" / "plugin.py"
    source.parent.mkdir(parents=True)
    source.write_text(
        "def fixture_seed():\n    raise TypeError('bad seed')\n", encoding="utf-8"
    )

    targets = _production_targets(
        tmp_path,
        r"..\..\..\.nfi\run\case\r1\p\src\demo\plugin.py:2: TypeError",
    )

    assert targets == ["src/demo/plugin.py:fixture_seed"]


def test_named_constructor_type_error_binds_unique_production_class(tmp_path):
    source = tmp_path / "src" / "demo.py"
    source.parent.mkdir()
    source.write_text(
        "class BrokenError(RuntimeError):\n"
        "    def __init__(self, value, required):\n"
        "        super().__init__(value)\n",
        encoding="utf-8",
    )

    target = _named_constructor_failure_target(
        tmp_path,
        "TypeError: BrokenError.__init__() missing 1 required positional argument: 'required'",
    )

    assert target == "src/demo.py:BrokenError.__init__"


def test_named_constructor_type_error_rejects_duplicate_class_identity(tmp_path):
    for name in ("one.py", "two.py"):
        (tmp_path / name).write_text(
            "class BrokenError(RuntimeError):\n"
            "    def __init__(self, value, required):\n"
            "        super().__init__(value)\n",
            encoding="utf-8",
        )

    assert _named_constructor_failure_target(
        tmp_path,
        "TypeError: BrokenError.__init__() missing 1 required positional argument: 'required'",
    ) is None


def test_missing_required_project_interpreter_does_not_fall_back(monkeypatch):
    monkeypatch.setattr("runtime.project_native_failure_environment._interpreter_candidates", lambda major, minor: [])

    resolution = _resolve_project_interpreter(
        "demo",
        {"project_interpreter_profiles": {"demo": {"major": 9, "minor": 9}}},
    )

    assert resolution["status"] == "unavailable"
    assert resolution["requested"] == "9.9"
    assert resolution["fallback_allowed"] is False


def test_empty_tool_overlay_does_not_digest_workspace(monkeypatch):
    monkeypatch.setattr(
        "runtime.project_native_failure_shard_cache._project_digest",
        lambda path: (_ for _ in ()).throw(AssertionError(f"unexpected digest: {path}")),
    )

    assert _configured_overlay_digest("") == "none"
    assert _configured_overlay_digest(None) == "none"
