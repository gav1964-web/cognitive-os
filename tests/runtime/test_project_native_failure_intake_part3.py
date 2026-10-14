from __future__ import annotations

from tests.runtime.project_native_failure_intake_helpers import *

def test_pytest9_compatibility_retry_requires_exact_collection_warning():
    output = (
        "ERROR collecting tests/test_basic.py\n"
        "pytest.PytestRemovedIn10Warning: Passing a non-Collection iterable to "
        "parametrize is deprecated."
    )

    assert _pytest9_collection_compatibility_failure(output) is True
    assert _pytest9_collection_compatibility_failure(
        output.replace("ERROR collecting", "FAILED")
    ) is False


def test_strict_default_failure_kind_requires_target_and_parameterized_case():
    target = "src/click/core.py:Option.get_help_extra"
    summary = "ValueError: cannot compare to string"
    nodeid = "tests/test_options.py::test_show_default_with_empty_string[non-string-comparable-object]"

    assert _failure_kind(target, summary, [nodeid]) == "strict_default_string_comparison_contract"
    assert _failure_kind(target, summary, []) is None


def test_nested_pytest_failure_preserves_outer_and_leaf_summaries(tmp_path):
    source = tmp_path / "src" / "plugin.py"
    source.parent.mkdir()
    source.write_text(
        "def faker_seed():\n    raise TypeError('bad seed')\n", encoding="utf-8"
    )
    output = (
        "FAILED tests/test_plugin.py::test_faker_enabled_disabled - AssertionError\n"
        "E   AssertionError: outer outcome mismatch\n"
        "E   TypeError: can only concatenate str (not \"int\") to str\n"
        f"{source}:2: TypeError\n"
    )

    result = _interpret_pytest_result(tmp_path, 1, output, {})

    assert result["failure_summary"] == "AssertionError: outer outcome mismatch"
    assert result["leaf_failure_summary"] == (
        'TypeError: can only concatenate str (not "int") to str'
    )
    assert _failure_kind(
        result["leaf_production_target"],
        result["leaf_failure_summary"],
        result["failing_nodeids"],
    ) == "disabled_pytest_plugin_symbolic_seed_contract"


def test_readiness_cleanup_failure_kind_requires_target_and_regression_nodeid():
    target = "pytest_httpserver/httpserver.py:HTTPServer.start"
    nodeids = ["tests/test_readiness.py::test_readiness_failure_stops_server"]

    assert _failure_kind(target, "1 failed", nodeids) == (
        "server_start_readiness_cleanup_contract"
    )
    assert _failure_kind(target, "1 failed", []) is None


def test_pickle_reconstruction_failure_kind_requires_named_constructor_and_nodeid():
    target = "src/pytest_socket/__init__.py:SocketConnectBlockedError.__init__"
    summary = (
        "TypeError: SocketConnectBlockedError.__init__() missing 1 required "
        "positional argument: 'host'"
    )
    nodeids = ["tests/test_socket.py::test_exceptions_are_pickleable[exc1]"]

    assert _failure_kind(target, summary, nodeids) == (
        "exception_pickle_reconstruction_contract"
    )
    assert _failure_kind(target, summary, []) is None


def test_windows_nonblocking_socket_capability_is_environment_blocker(tmp_path):
    result = _interpret_pytest_result(
        tmp_path,
        1,
        "FAILED tests/test_socket.py::test_send\n"
        "BlockingIOError: [WinError 10035] operation could not be completed immediately",
        {},
    )

    assert result["status"] == "environment_blocked"


def test_windows_oversized_nodeid_failure_is_bounded_environment_blocker(tmp_path):
    nodeid = "tests/test_parser.py::test_case[" + ("x" * 40000) + "]"
    result = _interpret_pytest_result(
        tmp_path,
        1,
        f"FAILED {nodeid}\nValueError: the environment variable is longer than 32767 characters",
        {"maximum_output_chars": 12000, "maximum_nodeid_chars": 1024},
    )

    assert result["status"] == "environment_blocked"
    assert len(result["failing_nodeids"][0]) == 1024


def test_explicit_optional_dependency_install_hint_is_environment_blocker(tmp_path):
    result = _interpret_pytest_result(
        tmp_path,
        1,
        "FAILED tests/test_crypto.py::test_address\n"
        "ImportError: Do `pip install validators[crypto]` to perform validation.",
        {},
    )

    assert result["status"] == "environment_blocked"
    assert result["failure_signature"] is None


def test_custom_module_not_installed_error_is_environment_blocker(tmp_path):
    result = _interpret_pytest_result(
        tmp_path,
        1,
        "FAILED tests/test_parser.py::test_links\n"
        "ModuleNotFoundError: Linkify enabled but not installed.",
        {},
    )

    assert result["status"] == "environment_blocked"
    assert result["production_targets"] == []


def test_source_fallback_plugin_metadata_failure_has_no_repair_authority(tmp_path):
    result = _interpret_pytest_result(
        tmp_path,
        1,
        "FAILED tests/integration/test_api.py::test_default\n"
        "src/flake8/plugins/reporter.py:40: in make\n"
        "WARNING 'default' is an unknown formatter. Falling back to default.\n"
        "KeyError: 'default'",
        {},
        environment_preparation={"status": "source_path_fallback"},
    )

    assert result["status"] == "environment_blocked"
    assert result["failure_signature"] is None
    assert result["environment_reason"] == "editable_install_required_for_plugin_metadata"


def test_installed_plugin_failure_is_not_hidden_by_metadata_guard(tmp_path):
    result = _interpret_pytest_result(
        tmp_path,
        1,
        "FAILED tests/integration/test_api.py::test_default\n"
        "src/demo/plugins/reporter.py:40: in make\n"
        "RuntimeError: plugin implementation failed",
        {},
        environment_preparation={"status": "ready"},
    )

    assert result["status"] == "test_failed"
    assert result["failure_signature"] is not None


def test_pytest_duration_does_not_change_failure_signature(tmp_path):
    first = _interpret_pytest_result(
        tmp_path, 1, "FAILED tests/test_api.py::test_case\n1 failed, 18 passed in 2.06s", {}
    )
    second = _interpret_pytest_result(
        tmp_path, 1, "FAILED tests/test_api.py::test_case\n1 failed, 18 passed in 1.22s", {}
    )

    assert first["failure_signature"] == second["failure_signature"]


def test_subtest_failure_binds_class_method_assertion_to_production(tmp_path):
    project = tmp_path / "library"
    (project / "tests").mkdir(parents=True)
    (project / "src" / "demo").mkdir(parents=True)
    (project / "src" / "demo" / "split.py").write_text(
        "def split_before(values):\n    return [values]\n", encoding="utf-8"
    )
    (project / "tests" / "test_split.py").write_text(
        "from demo.split import split_before\n\n"
        "class SplitTests:\n"
        "    def test_empty(self):\n"
        "        actual = split_before([])\n"
        "        assert actual == []\n",
        encoding="utf-8",
    )
    output = (
        "SUBFAILED(maxsplit=0) tests/test_split.py::SplitTests::test_empty\n"
        "AssertionError: [[]] != []\n1 failed in 0.1s"
    )

    result = _interpret_pytest_result(project, 1, output, {})

    assert result["status"] == "test_failed"
    assert result["failing_nodeids"] == ["tests/test_split.py::SplitTests::test_empty"]
    assert result["production_targets"] == ["src/demo/split.py:split_before"]
    assert result["target_binding"] == "unique_assertion_causal_call"


def test_unique_local_star_reexport_resolves_to_defining_module(tmp_path):
    project = tmp_path / "library"
    (project / "tests").mkdir(parents=True)
    (project / "src" / "demo").mkdir(parents=True)
    (project / "src" / "demo" / "__init__.py").write_text(
        "from .operations import *\n", encoding="utf-8"
    )
    (project / "src" / "demo" / "operations.py").write_text(
        "def split_before(values):\n    return [values]\n", encoding="utf-8"
    )
    (project / "tests" / "test_split.py").write_text(
        "import demo\n\ndef test_empty():\n    assert demo.split_before([]) == []\n",
        encoding="utf-8",
    )

    result = _interpret_pytest_result(
        project, 1, "FAILED tests/test_split.py::test_empty\nAssertionError: [[]] != []", {}
    )

    assert result["production_targets"] == ["src/demo/operations.py:split_before"]


def test_direct_test_helper_does_not_bind_as_production(tmp_path):
    project = tmp_path / "library"
    (project / "tests").mkdir(parents=True)
    (project / "tests" / "common.py").write_text("class Helper:\n    pass\n", encoding="utf-8")
    (project / "tests" / "test_api.py").write_text(
        "from tests.common import Helper\n\ndef test_case():\n    Helper()\n",
        encoding="utf-8",
    )

    assert _direct_test_call_targets(project, ["tests/test_api.py::test_case"]) == []


def test_unique_direct_imported_test_call_binds_production_target(tmp_path):
    project = tmp_path / "library"
    (project / "src" / "demo").mkdir(parents=True)
    (project / "tests").mkdir()
    (project / "src" / "demo" / "__init__.py").write_text("", encoding="utf-8")
    (project / "src" / "demo" / "utils.py").write_text(
        "def normalize(value):\n    return value.strip()\n",
        encoding="utf-8",
    )
    (project / "tests" / "test_utils.py").write_text(
        "from demo import utils\n\ndef test_normalize():\n    assert utils.normalize(' x ') == 'x'\n",
        encoding="utf-8",
    )

    targets = _direct_test_call_targets(
        project, ["tests/test_utils.py::test_normalize"]
    )

    assert targets == ["src/demo/utils.py:normalize"]


def test_tuple_unpacked_result_binds_static_class_method(tmp_path):
    project = tmp_path / "library"
    (project / "src" / "demo").mkdir(parents=True)
    (project / "tests").mkdir()
    (project / "src" / "demo" / "__init__.py").write_text("", encoding="utf-8")
    (project / "src" / "demo" / "processor.py").write_text(
        "class Processor:\n"
        "    def transform(self):\n"
        "        return [], ['ok'], []\n",
        encoding="utf-8",
    )
    (project / "tests" / "test_processor.py").write_text(
        "from demo import processor\n\n"
        "def test_transform():\n"
        "    instance = processor.Processor()\n"
        "    _, logical, _ = processor.Processor.transform(instance)\n"
        "    assert logical == ['ok']\n",
        encoding="utf-8",
    )

    targets = _direct_test_call_targets(
        project, ["tests/test_processor.py::test_transform"]
    )

    assert targets == ["src/demo/processor.py:Processor.transform"]


def test_multiple_direct_production_calls_remain_unbound(tmp_path):
    project = tmp_path / "library"
    (project / "src" / "demo").mkdir(parents=True)
    (project / "tests").mkdir()
    (project / "src" / "demo" / "__init__.py").write_text("", encoding="utf-8")
    (project / "src" / "demo" / "utils.py").write_text(
        "def first():\n    return 1\n\ndef second():\n    return 2\n",
        encoding="utf-8",
    )
    (project / "tests" / "test_utils.py").write_text(
        "from demo import utils\n\ndef test_both():\n    assert utils.first() == utils.second()\n",
        encoding="utf-8",
    )

    assert _direct_test_call_targets(project, ["tests/test_utils.py::test_both"]) == []


def test_assertion_causal_slice_ignores_unrelated_setup_call(tmp_path):
    project = tmp_path / "library"
    (project / "src" / "demo").mkdir(parents=True)
    (project / "tests").mkdir()
    (project / "src" / "demo" / "__init__.py").write_text("", encoding="utf-8")
    (project / "src" / "demo" / "utils.py").write_text(
        "def configure():\n    return None\n\ndef normalize(value):\n    return value.strip()\n",
        encoding="utf-8",
    )
    (project / "tests" / "test_utils.py").write_text(
        "from demo.utils import configure, normalize\n\n"
        "def test_normalize():\n"
        "    configure()\n"
        "    result = normalize(' x ')\n"
        "    assert result == 'x'\n",
        encoding="utf-8",
    )

    targets = _direct_test_call_targets(
        project, ["tests/test_utils.py::test_normalize"]
    )

    assert targets == ["src/demo/utils.py:normalize"]


def test_test_observer_and_instance_runner_remain_diagnostically_unbound(tmp_path):
    project = tmp_path / "cli"
    (project / "tests").mkdir(parents=True)
    (project / "tests" / "utils.py").write_text(
        "def normalize_output(value):\n    return value.strip()\n", encoding="utf-8"
    )
    (project / "tests" / "test_cli.py").write_text(
        "from tests.utils import normalize_output\n\n"
        "def test_cli():\n"
        "    result = runner.invoke(app)\n"
        "    normalized = normalize_output(result.output)\n"
        "    assert 'styled' in normalized\n",
        encoding="utf-8",
    )

    result = _interpret_pytest_result(
        project,
        1,
        "FAILED tests/test_cli.py::test_cli\n1 failed in 0.1s",
        {},
    )

    assert result["production_targets"] == []
    assert result["causal_analysis"]["reason"] == "no_project_production_target_in_assertion_slice"
    assert {row["reason"] for row in result["causal_analysis"]["excluded_calls"]} == {
        "test_support_call",
        "local_or_instance_call",
    }


def test_imported_test_observer_is_an_opaque_causal_boundary(tmp_path):
    project = tmp_path / "library"
    (project / "rich").mkdir(parents=True)
    (project / "tests").mkdir()
    (project / "rich" / "__init__.py").write_text("", encoding="utf-8")
    (project / "rich" / "card.py").write_text(
        "def make_card():\n    return object()\n", encoding="utf-8"
    )
    (project / "tests" / "helpers.py").write_text(
        "def render(value):\n    return str(value)\n", encoding="utf-8"
    )
    (project / "tests" / "test_card.py").write_text(
        "from rich.card import make_card\n"
        "from tests.helpers import render\n\n"
        "def test_card():\n"
        "    card = make_card()\n"
        "    result = render(card)\n"
        "    assert result == 'expected'\n",
        encoding="utf-8",
    )

    result = _interpret_pytest_result(
        project,
        1,
        "FAILED tests/test_card.py::test_card\n1 failed in 0.1s",
        {},
    )

    assert result["production_targets"] == []
    assert result["causal_analysis"]["candidate_targets"] == []
    assert result["causal_analysis"]["excluded_calls"] == [
        {"call": "render", "reason": "test_support_call"},
        {"call": "make_card", "reason": "opaque_observer_descendant"},
    ]
