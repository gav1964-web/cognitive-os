import sys

from runtime.contract_archetype_inference import contract_archetype_for_target
from runtime.executable_acceptance_loading import import_path, load_supported_callable
from runtime.executable_acceptance_materializers import materialize
from runtime.executable_acceptance_policy import sample_value
from runtime.executable_acceptance_isolation import load_source_isolated_callable
from runtime.executable_acceptance_support import positive_samples_execute
from runtime.programmer_patch_synthesizer import _guard_required_keys
from runtime.programmer_verification import _run_project_scoped_verification
from runtime.source_contract_semantics import infer_source_contract


def test_python2_callable_body_remains_available_for_contract_analysis():
    evidence = infer_source_contract(
        {
            "signature": {"args": [{"name": "panel"}]},
            "snippet": {
                "text": "def fix(panel):\n    print panel['name']\n    panel['name'] = 'normalized'\n"
            },
        }
    )

    assert evidence["source_body_available"] is True
    assert evidence["source_body_complete"] is True
    assert evidence["state_mutation"] is True


def test_iteration11_contract_families_are_generalized():
    targets = {
        "scripts/backup.py:getOpt": "cli_argument_parsing_boundary",
        "apply-framework.py:get_projects": "external_resource_collection_query",
        "backend/app/core/config.py:assemble_cors_origins": "configuration_collection_normalizer",
        "api/websocket/functions.py:disconnect": "async_connection_lifecycle_transition",
        "dataset/bitmachines.py:gen_instance": "dataset_instance_generation_boundary",
    }

    for target, family in targets.items():
        assert contract_archetype_for_target(target)["contract_family"] == family


def test_python2_guard_analysis_does_not_abort_executor():
    source = "def fix(panel):\n    print panel['name']\n    panel['name'] = 'normalized'\n"

    assert _guard_required_keys(source, "fix", ["panel"]) == ["panel"]


def test_project_scoped_verifier_accepts_identified_python2_source(tmp_path):
    (tmp_path / "legacy.py").write_text(
        "def show(value):\n    print value\n",
        encoding="utf-8",
    )

    result = _run_project_scoped_verification(
        tmp_path,
        {"expected_files": ["legacy.py"]},
    )

    assert result["status"] == "passed"
    assert result["compatibility_modes"] == {
        "legacy.py": "python2_compatibility_ast"
    }


def test_unbounded_module_loop_is_source_isolated_before_import(tmp_path):
    source = tmp_path / "worker.py"
    source.write_text(
        "def run_pending():\n    return 'ok'\n\nwhile True:\n    pass\n",
        encoding="utf-8",
    )

    loaded = load_supported_callable(tmp_path, "worker.py", "run_pending", source)

    assert loaded["source_isolated"] is True
    assert loaded["callable"]() == "ok"


def test_cli_system_exit_becomes_failed_sample_not_process_exit():
    def parse_options(argv):
        raise SystemExit(2)

    obligations = [
        {"target": "cli.py:parse_options", "kind": "positive_contract_case", "given": {"argv": ["--bad"]}}
    ]

    assert positive_samples_execute(parse_options, "cli.py:parse_options", obligations) is False


def test_top_level_system_exit_becomes_import_failure_not_process_exit(tmp_path):
    source = tmp_path / "app.py"
    source.write_text(
        "import sys\ndef handler():\n    return 'ok'\nsys.exit(0)\n",
        encoding="utf-8",
    )

    with import_path(tmp_path):
        loaded = load_supported_callable(tmp_path, "app.py", "handler", source)

    assert loaded["callable"] is None
    assert loaded["reason"] == "import_failed_runtime_error"
    assert loaded["detail"] == "0"


def test_python2_function_can_run_through_source_isolation(tmp_path):
    source = tmp_path / "legacy.py"
    source.write_text(
        "def normalize(panel):\n    print panel['name']\n    return panel['name']\n",
        encoding="utf-8",
    )

    loaded = load_source_isolated_callable(source, "normalize")

    assert loaded["reason"] == ""
    assert loaded["callable"]({"name": "status"}) == "status"


def test_source_isolated_method_infers_safe_read_only_instance_attribute(tmp_path):
    source = tmp_path / "client.py"
    source.write_text(
        "class Client:\n"
        "    def wait(self):\n        return None\n"
        "    def check(self):\n"
        "        self.socket.setblocking(False)\n"
        "        return self.wait()\n",
        encoding="utf-8",
    )

    loaded = load_source_isolated_callable(source, "check")

    assert loaded["reason"] == ""
    assert loaded["callable"]() is None
    assert loaded["method_instance_attributes"] == {
        "socket": {"__fixture__": "safe_method_attribute"}
    }


def test_source_isolated_method_materializes_attributes_assigned_by_unrun_init(tmp_path):
    source = tmp_path / "widget.py"
    source.write_text(
        "class Widget:\n"
        "    def __init__(self):\n"
        "        self.disabled = False\n"
        "        self.label = 'ready'\n"
        "    def render(self):\n"
        "        if self.disabled:\n"
        "            return ''\n"
        "        return self.label.upper()\n",
        encoding="utf-8",
    )

    loaded = load_source_isolated_callable(source, "Widget.render")

    assert loaded["reason"] == ""
    assert loaded["callable"]() is not None
    assert set(loaded["method_instance_attributes"]) == {"disabled", "label"}


def test_source_isolation_keeps_required_guarded_import(tmp_path):
    source = tmp_path / "callback.py"
    source.write_text(
        "try:\n    import optional_events\nexcept ImportError:\n    optional_events = None\n\n"
        "class Callback:\n"
        "    def record(self, value):\n"
        "        optional_events.add(value)\n",
        encoding="utf-8",
    )

    loaded = load_source_isolated_callable(source, "record")

    assert loaded["reason"] == ""
    assert loaded["callable"]("sample") is None


def test_source_isolated_staticmethod_initializes_fixture_evidence(tmp_path):
    source = tmp_path / "subject.py"
    source.write_text(
        "class Subject:\n"
        "    @staticmethod\n"
        "    def generate(value):\n"
        "        return value.upper()\n",
        encoding="utf-8",
    )

    loaded = load_source_isolated_callable(source, "generate")

    assert loaded["reason"] == ""
    assert loaded["callable"]("ok") == "OK"
    assert loaded["method_instance_attributes"] == {}


def test_source_isolated_method_ignores_unrelated_class_assignment(tmp_path):
    source = tmp_path / "settings.py"
    source.write_text(
        "from missing_framework import incompatible_factory\n\n"
        "class Settings:\n"
        "    unrelated = incompatible_factory(regex='legacy')\n"
        "    def normalize(self, value):\n"
        "        return value.strip()\n",
        encoding="utf-8",
    )

    loaded = load_source_isolated_callable(source, "normalize")

    assert loaded["reason"] == ""
    assert loaded["callable"](" ok ") == "ok"


def test_source_isolated_staticmethod_keeps_referenced_class_attribute(tmp_path):
    source = tmp_path / "hashing.py"
    source.write_text(
        "from passlib.context import CryptContext\n\n"
        "class Hasher:\n"
        "    pwd_context = CryptContext(schemes=['bcrypt'])\n"
        "    @staticmethod\n"
        "    def verify_password(plain, encoded):\n"
        "        return Hasher.pwd_context.verify(plain, encoded)\n",
        encoding="utf-8",
    )

    loaded = load_source_isolated_callable(source, "verify_password")

    assert loaded["reason"] == ""
    assert loaded["callable"]("plain", "encoded") is True


def test_source_isolated_callable_stubs_function_local_effect_import(tmp_path):
    source = tmp_path / "clock.py"
    source.write_text(
        "def sync_clock():\n"
        "    from ntptime import settime\n"
        "    settime()\n",
        encoding="utf-8",
    )

    loaded = load_source_isolated_callable(source, "sync_clock")

    assert loaded["callable"]() is None
    assert loaded["effect_module_stubs"] == ["ntptime"]


def test_source_isolated_callable_stubs_context_managed_effect_client(tmp_path):
    source = tmp_path / "mail.py"
    source.write_text(
        "import smtplib\n"
        "def send(message):\n"
        "    with smtplib.SMTP('example.test', 25) as client:\n"
        "        client.sendmail('from', 'to', message)\n",
        encoding="utf-8",
    )

    loaded = load_source_isolated_callable(source, "send")

    assert loaded["callable"]("hello") is None
    assert loaded["effect_module_stubs"] == ["smtplib"]


def test_source_isolation_resolves_relative_resource_read_only(tmp_path):
    source = tmp_path / "helpers" / "email.py"
    source.parent.mkdir()
    (tmp_path / "templates").mkdir()
    (tmp_path / "templates" / "email.txt").write_text("hello {{ name }}", encoding="utf-8")
    source.write_text(
        "def render(name):\n"
        "    with open('templates/email.txt') as stream:\n"
        "        return stream.read().replace('{{ name }}', name)\n",
        encoding="utf-8",
    )

    loaded = load_source_isolated_callable(source, "render")

    assert loaded["reason"] == ""
    assert loaded["callable"]("Ada") == "hello Ada"


def test_source_isolation_uses_conservative_external_probe_flags(tmp_path):
    source = tmp_path / "feature.py"
    source.write_text(
        "import unavailable_environment\n"
        "ENABLED, PLATFORM, ROOT = unavailable_environment.probe()\n"
        "def enabled():\n"
        "    return ENABLED\n",
        encoding="utf-8",
    )

    loaded = load_source_isolated_callable(source, "enabled")

    assert loaded["reason"] == ""
    assert loaded["callable"]() is False


def test_source_isolation_materializes_unresolved_wildcard_names(tmp_path):
    source = tmp_path / "scene.py"
    source.write_text(
        "from missing_visuals import *\n"
        "class Scene:\n"
        "    def construct(self):\n"
        "        plane = NumberPlane()\n"
        "        self.play(Create(plane))\n",
        encoding="utf-8",
    )

    load_supported_callable(tmp_path, "scene.py", "construct", source)
    loaded = load_source_isolated_callable(source, "construct")

    assert loaded["reason"] == ""
    assert loaded["callable"]() is None
    assert loaded["wildcard_import_stubs"] == ["Create", "NumberPlane"]


def test_source_isolation_uses_configured_path_bound_constructor(tmp_path):
    source = tmp_path / "app.py"
    source.write_text(
        "from starlette.staticfiles import StaticFiles\n"
        "def build_static():\n"
        "    return StaticFiles(directory='missing-static')\n",
        encoding="utf-8",
    )

    loaded = load_source_isolated_callable(source, "build_static")

    assert loaded["reason"] == ""
    assert loaded["callable"]() is not None
    assert loaded["effect_module_stubs"] == ["configured:StaticFiles"]


def test_source_isolation_keeps_required_module_level_class(tmp_path):
    source = tmp_path / "scanner.py"
    source.write_text(
        "class Result:\n"
        "    def __init__(self, value):\n        self.value = value\n"
        "class Scanner:\n"
        "    def scan(self, value):\n        return Result(value).value\n",
        encoding="utf-8",
    )

    loaded = load_source_isolated_callable(source, "scan")

    assert loaded["reason"] == ""
    assert loaded["callable"]("ok") == "ok"


def test_source_isolation_orders_global_assignment_dependencies(tmp_path):
    source = tmp_path / "matcher.py"
    source.write_text(
        "left = 'a'\n"
        "right = 'b'\n"
        "combined = left + right\n"
        "def match(value):\n    return value == combined\n",
        encoding="utf-8",
    )

    loaded = load_source_isolated_callable(source, "match")

    assert loaded["reason"] == ""
    assert loaded["callable"]("ab") is True


def test_source_isolation_does_not_leak_imported_modules_between_projects(tmp_path):
    first = tmp_path / "first" / "subject.py"
    second = tmp_path / "second" / "subject.py"
    first.parent.mkdir()
    second.parent.mkdir()
    first.write_text(
        "import acceptance_probe_dependency\n"
        "def value():\n    return acceptance_probe_dependency.missing\n",
        encoding="utf-8",
    )
    second.write_text(
        "def value():\n    return 'clean'\n",
        encoding="utf-8",
    )

    first_loaded = load_source_isolated_callable(first, "value")
    second_loaded = load_source_isolated_callable(second, "value")

    assert first_loaded["reason"] == ""
    assert first_loaded["callable"]() is not None
    assert second_loaded["callable"]() == "clean"
    assert "acceptance_probe_dependency" not in sys.modules


def test_general_boundary_samples_are_config_backed():
    assert sample_value("", "argv") == ["program"]
    assert sample_value("", "optional_variables") == "unused:value"
    event = materialize(sample_value("", "evt"))
    client = materialize(sample_value("", "gl"))
    inventory = materialize(sample_value("", "input_dictionary"))
    cube = materialize(sample_value("", "input_array"))

    assert event.detail == {"module_name": "not_loaded"}
    assert client.groups.get("group").projects.list(all=True) == []
    assert len(inventory) == 3
    assert len(materialize({"input_dictionary": {}})["input_dictionary"]) == 3
    assert cube.shape == (2, 2, 1)
    assert sample_value("", "N") == 8
