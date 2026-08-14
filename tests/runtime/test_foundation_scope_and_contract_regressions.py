from pathlib import Path

from runtime._parts.role_foundation_field_trial_scope import _primary_language_scope
from runtime._parts import role_foundation_pipeline_part4 as scope_pipeline
from runtime.contract_archetype_inference import contract_archetype_for_target
from runtime.role_foundation_pipeline import _auto_active_root_decision
from runtime.technical_spec_policy import load_technical_spec_policy


def test_scope_rejects_independent_project_collection(tmp_path):
    for index in range(10):
        member = tmp_path / "Projects" / f"{index}_demo"
        member.mkdir(parents=True)
        (member / "app.py").write_text("def run():\n    return 1\n", encoding="utf-8")

    result = _primary_language_scope(tmp_path)

    assert result["status"] == "out_of_scope"
    assert result["reason_code"] == "no_python_owned_product_boundary"


def test_scope_rejects_nested_tutorial_and_support_only_python(tmp_path):
    tutorial = tmp_path / "course" / "docker" / "step3"
    tutorial.mkdir(parents=True)
    (tutorial / "main.py").write_text("print('lesson')\n", encoding="utf-8")

    result = _primary_language_scope(tmp_path)

    assert result["status"] == "out_of_scope"
    assert result["reason_code"] == "no_python_owned_product_boundary"


def test_scope_rejects_root_installation_helpers_without_product(tmp_path):
    (tmp_path / "meson_post_install.py").write_text("print('install')\n", encoding="utf-8")
    (tmp_path / "kill.py").write_text("print('stop helper')\n", encoding="utf-8")

    assert _primary_language_scope(tmp_path)["status"] == "out_of_scope"


def test_scope_keeps_small_root_and_src_products(tmp_path):
    (tmp_path / "product.py").write_text("def run(): return 1\n", encoding="utf-8")
    assert _primary_language_scope(tmp_path)["status"] == "in_scope"

    (tmp_path / "product.py").unlink()
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "product.py").write_text("def run(): return 1\n", encoding="utf-8")
    assert _primary_language_scope(tmp_path)["status"] == "in_scope"


def test_auto_scope_selects_real_root_package_over_higher_scored_workflow(tmp_path):
    (tmp_path / "workflow").mkdir()
    package = tmp_path / "temnn"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    candidates = [
        {"path": "workflow", "score": 70, "python_files": 71},
        {"path": "temnn", "score": 48, "python_files": 22},
    ]

    decision = _auto_active_root_decision(tmp_path, {"candidate_roots": candidates})

    assert decision["status"] == "selected"
    assert Path(decision["selected_root"]).resolve() == package.resolve()
    assert decision["source"] == "auto_root_python_package_scope_selector"


def test_auto_scope_selects_substantial_python_automation_boundary(tmp_path):
    (tmp_path / "images").mkdir()
    automation = tmp_path / "ci"
    automation.mkdir()
    candidates = [
        {"path": "images", "score": 50, "python_files": 5, "js_ts_files": 0},
        {"path": "ci", "score": 18, "python_files": 20, "js_ts_files": 3},
    ]

    decision = _auto_active_root_decision(tmp_path, {"candidate_roots": candidates})

    assert decision["status"] == "selected"
    assert Path(decision["selected_root"]).resolve() == automation.resolve()
    assert decision["source"] == "auto_python_automation_scope_selector"


def test_auto_scope_does_not_promote_small_ci_helper_collection(tmp_path):
    (tmp_path / "ci").mkdir()

    decision = _auto_active_root_decision(
        tmp_path,
        {"candidate_roots": [{"path": "ci", "score": 18, "python_files": 2, "js_ts_files": 0}]},
    )

    assert decision["status"] != "selected"


def test_auto_scope_strategy_order_is_policy_driven(tmp_path, monkeypatch):
    package = tmp_path / "product"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    automation = tmp_path / "ci"
    automation.mkdir()
    candidates = [
        {"path": "product", "score": 60, "python_files": 20, "js_ts_files": 0},
        {"path": "ci", "score": 18, "python_files": 20, "js_ts_files": 0},
    ]
    original = scope_pipeline.scope_policy_list

    def reordered(field_name):
        if field_name == "auto_selector_strategy_order":
            return ["python_automation", "root_python_package"]
        return original(field_name)

    monkeypatch.setattr(scope_pipeline, "scope_policy_list", reordered)

    decision = scope_pipeline._auto_active_root_decision(tmp_path, {"candidate_roots": candidates})

    assert Path(decision["selected_root"]).resolve() == automation.resolve()
    assert decision["source"] == "auto_python_automation_scope_selector"


def test_scope_rejects_large_distributed_project_portfolio(tmp_path):
    for root_index in range(4):
        root = tmp_path / f"area_{root_index}"
        for project_index in range(5):
            project = root / f"project_{project_index}"
            project.mkdir(parents=True)
            (project / "requirements.txt").write_text("requests\n", encoding="utf-8")
        for module_index in range(250):
            (root / f"module_{module_index}.py").write_text("VALUE = 1\n", encoding="utf-8")

    result = _primary_language_scope(tmp_path)

    assert result["status"] == "out_of_scope"
    assert result["reason_code"] == "no_python_owned_product_boundary"


def test_scope_ignores_example_fixture_when_root_cli_is_product(tmp_path):
    (tmp_path / "scenarios" / "example_fixture").mkdir(parents=True)
    (tmp_path / "scenarios" / "example_fixture" / "verify.py").write_text("def run():\n    return 1\n")
    (tmp_path / "product.py").write_text("def deploy():\n    return True\n")

    result = _primary_language_scope(tmp_path)

    assert result["status"] == "in_scope"


def test_scope_rejects_integration_fixtures_without_product_source(tmp_path):
    fixture = tmp_path / "integration-test" / "models" / "dummy-chat"
    fixture.mkdir(parents=True)
    (fixture / "model.py").write_text("class Model: pass\n", encoding="utf-8")

    result = _primary_language_scope(tmp_path)

    assert result["status"] == "out_of_scope"
    assert result["python_source_files"] == 0


def test_scope_rejects_documentation_led_demo(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "data").mkdir()
    (tmp_path / "src" / "classify.py").write_text("print('demo')\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("guide\n" * 5_000, encoding="utf-8")

    result = _primary_language_scope(tmp_path)

    assert result["status"] == "out_of_scope"
    assert result["reason_code"] == "no_python_owned_product_boundary"


def test_scope_rejects_documentation_glossary_code_examples(tmp_path):
    for dirname in ("code", "docs", "notebooks"):
        (tmp_path / dirname).mkdir()
    for name in ("cnn.py", "knn.py", "loss_functions.py"):
        (tmp_path / "code" / name).write_text("def example(): return 1\n", encoding="utf-8")

    result = _primary_language_scope(tmp_path)

    assert result["status"] == "out_of_scope"
    assert result["reason_code"] == "no_python_owned_product_boundary"


def test_scope_rejects_documentation_index_with_fetch_script(tmp_path):
    (tmp_path / "README.md").write_text("[paper](https://example.test)\n" * 1_000, encoding="utf-8")
    (tmp_path / "fetch_papers.py").write_text("print('refresh index')\n", encoding="utf-8")

    result = _primary_language_scope(tmp_path)

    assert result["status"] == "out_of_scope"
    assert result["reason_code"] == "no_python_owned_product_boundary"


def test_scope_rejects_cython_extension_without_python_core(tmp_path):
    package = tmp_path / "ocr"
    package.mkdir()
    (tmp_path / "setup.py").write_text("from setuptools import setup\n", encoding="utf-8")
    (package / "__init__.py").write_text("from .ocr import Engine\n", encoding="utf-8")
    (package / "ocr.pyx").write_text("cdef class Engine:\n    pass\n", encoding="utf-8")

    result = _primary_language_scope(tmp_path)

    assert result["status"] == "out_of_scope"
    assert result["primary_language"] == "Cython native extension"


def test_scope_rejects_cpp_core_with_python_grpc_test_support(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "grpc_test").mkdir()
    for index in range(10):
        (tmp_path / "src" / f"core_{index}.cpp").write_text("int run() { return 1; }\n", encoding="utf-8")
    for index in range(9):
        (tmp_path / "grpc_test" / f"client_{index}.py").write_text("def run(): return 1\n", encoding="utf-8")

    result = _primary_language_scope(tmp_path)

    assert result["status"] == "out_of_scope"
    assert result["primary_language"] == "C++"


def test_scope_rejects_incidental_python_in_non_python_automation(tmp_path):
    lesson = tmp_path / "ansible" / "40-container-example"
    lesson.mkdir(parents=True)
    for index in range(5):
        (lesson / f"helper_{index}.py").write_text("def run(): return 1\n", encoding="utf-8")

    result = _primary_language_scope(tmp_path)

    assert result["status"] == "out_of_scope"
    assert result["reason_code"] == "no_python_owned_product_boundary"


def test_auto_scope_selects_standalone_python_project_in_monorepo(tmp_path):
    (tmp_path / "testing").mkdir()
    engine = tmp_path / "engine"
    engine.mkdir()
    (engine / "pyproject.toml").write_text("[project]\nname='engine'\n", encoding="utf-8")
    candidates = [
        {"path": "testing", "score": 110, "python_files": 26, "js_ts_files": 62},
        {"path": "component", "score": 110, "python_files": 811, "js_ts_files": 249},
        {"path": "engine", "score": 70, "python_files": 82, "js_ts_files": 0},
    ]

    decision = _auto_active_root_decision(tmp_path, {"candidate_roots": candidates})

    assert Path(decision["selected_root"]).resolve() == engine.resolve()
    assert decision["source"] == "auto_standalone_python_project_scope_selector"


def test_metric_and_model_query_contract_families_are_profiled():
    assert contract_archetype_for_target("sdk/client.py:__parse_response")["contract_archetype"] == (
        "sdk_response_parse_verification"
    )
    assert contract_archetype_for_target("Augmentor/Pipeline.py:keras_generator_from_array")["contract_archetype"] == (
        "array_batch_generator"
    )
    assert contract_archetype_for_target("oauth/compliance/slack.py:slack_compliance_fix")["contract_archetype"] == (
        "oauth_compliance_hook"
    )
    assert contract_archetype_for_target("dns/_ddr.py:ddr_tls_check_async")["contract_archetype"] == (
        "async_tls_validation_boundary"
    )
    assert contract_archetype_for_target("sketch/metrics.py:binary_metrics")["contract_archetype"] == (
        "metric_comparison_transform"
    )
    assert contract_archetype_for_target("purchase/model.py:query")["contract_archetype"] == "model_query_boundary"
    assert contract_archetype_for_target("httpcore/_async/http2.py:handle_async_request") == {}


def test_d14_contract_families_are_profiled_without_project_names():
    cases = {
        "account_outputs.py:_add_token_to_remote_pool": "remote_pool_import_transaction",
        "src/wifi/mixin.py:scan": "wireless_scan_state_reconciliation",
        "vcs/core.py:_safe_restore": "vcs_stash_restore_transaction",
        "socialscan/util.py:query": "async_identity_availability_query",
        "gateway/client.py:heartbeat": "protocol_heartbeat_loop",
        "tracking/processing_utils.py:sample_target_adaptive": "adaptive_image_target_crop",
        "face/MTCNN.py:predict_onet": "multi_head_image_inference",
    }

    for target, expected in cases.items():
        assert contract_archetype_for_target(target)["contract_archetype"] == expected


def test_d15_contract_families_are_profiled_without_project_names():
    assert contract_archetype_for_target("hooks/unittest.py:set_hook_for_unittest_module_teardown")[
        "contract_archetype"
    ] == "test_lifecycle_instrumentation_wrapper"
    assert contract_archetype_for_target("cli/display.py:display_csv")["contract_archetype"] == (
        "tabular_csv_serialization"
    )


def test_d16_async_sdk_request_adapter_is_profiled_without_project_name():
    profile = contract_archetype_for_target("api/stats.py:broadcast_stats_req")

    assert profile["contract_archetype"] == "async_sdk_request_adapter"
    assert profile["side_effect_policy"]["requires_validation_gate"] is True
    assert contract_archetype_for_target("jobs/worker.py:enqueue_req") == {}


def test_process_boundary_override_does_not_allow_known_too_broad_profile():
    override = load_technical_spec_policy()["process_boundary_review_override"]

    assert override["enabled"] is False
    assert "legacy_batch_orchestrator_too_broad" not in override["required_profile_ids"]
