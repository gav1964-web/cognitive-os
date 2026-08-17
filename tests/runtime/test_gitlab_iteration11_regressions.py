from runtime.contract_archetype_inference import contract_archetype_for_target
from runtime.executable_acceptance_loading import load_supported_callable
from runtime.executable_acceptance_support import positive_samples_execute
from runtime.programmer_patch_synthesizer import _guard_required_keys
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
