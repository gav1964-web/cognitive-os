from runtime.contract_archetype_inference import contract_archetype_for_target
from runtime.executable_acceptance_loading import load_supported_callable
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


def test_general_boundary_samples_are_config_backed():
    assert sample_value("", "argv") == ["program"]
    assert sample_value("", "optional_variables") == "unused:value"
    event = materialize(sample_value("", "evt"))
    client = materialize(sample_value("", "gl"))
    inventory = materialize(sample_value("", "input_dictionary"))

    assert event.detail == {"module_name": "not_loaded"}
    assert client.groups.get("group").projects.list(all=True) == []
    assert len(inventory) == 3
    assert len(materialize({"input_dictionary": {}})["input_dictionary"]) == 3
