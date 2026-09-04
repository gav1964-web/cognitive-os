from __future__ import annotations

from tests.runtime.first_slice_viability_helpers import *

def test_kb_defers_ml_lifecycle_and_prefers_bounded_mapping():
    training = first_slice_viability(
        "model/network.py:train",
        knowledge_rule="scientific_compute_library",
    )
    mapping = first_slice_viability(
        "dataset/randgraph.py:cmd_to_vec",
        knowledge_rule="scientific_compute_library",
    )

    assert training["status"] == "deferred"
    assert training["reselection_required"] is True
    assert training["score"] == -70
    assert mapping["status"] == "eligible"
    assert mapping["score"] == 24


def test_viability_accepts_plain_text_snippet_context():
    result = first_slice_viability(
        "basics.py",
        {"snippet": "print('hello')", "dependency_readiness": "unknown"},
        knowledge_rule="project_map_report_minimal_extraction_plan",
    )

    assert result["status"] in {"eligible", "deferred"}


def test_receiver_state_method_is_deferred_but_static_method_remains_eligible():
    method = first_slice_viability(
        "utils/config.py:load",
        {"snippet": {"target_binding": "method_symbol", "owner_class": "Config", "text": "def load(self): return self.path"}},
    )
    static = first_slice_viability(
        "utils/config.py:load",
        {"snippet": {"target_binding": "method_symbol", "owner_class": "Config", "decorators": ["staticmethod"]}},
    )

    assert method["status"] == "deferred"
    assert method["reselection_required"] is True
    assert static["status"] == "eligible"


def test_runtime_lifecycle_and_cli_boundaries_require_cheaper_slice():
    lifecycle = first_slice_viability("runtime/worker.py:execute")
    close = first_slice_viability("adapter.py:close")
    flush = first_slice_viability("adapter.py:force_flush")
    cli = first_slice_viability("pkg/cli/base.py:main")
    cli_helper = first_slice_viability("pkg/cli/base.py:list_templates")
    training = first_slice_viability("models/network.py:train_model")

    assert lifecycle["reselection_required"] is True
    assert close["reselection_required"] is True
    assert flush["reselection_required"] is True
    assert cli["reselection_required"] is True
    assert cli_helper["reselection_required"] is False
    assert training["reselection_required"] is True


def test_runtime_decorator_factory_requires_event_loop_fixture():
    result = first_slice_viability(
        "runtime/slots.py:async_slot",
        {
            "snippet": {"text": "def async_slot(): ..."},
            "unresolved_calls": ["asyncio.create_task", "background_tasks.add"],
        },
    )

    assert result["status"] == "deferred"
    assert result["reselection_required"] is True


def test_dynamic_backend_selector_requires_installed_provider():
    result = first_slice_viability(
        "runtime/backend.py:select_backend",
        {"unresolved_calls": ["importlib.import_module", "os.getenv"]},
    )

    assert result["status"] == "deferred"
    assert result["reselection_required"] is True


def test_stateful_method_effects_remain_deferred():
    result = first_slice_viability(
        "utils/config.py:load",
        {
            "snippet": {"target_binding": "method_symbol", "owner_class": "Config"},
            "side_effects": ["memory_state"],
        },
    )

    assert result["score"] < 0
    assert any(row["rule_id"] == "stateful_method_effects" for row in result["matched_rules"])


def test_stateful_free_function_requires_explicit_state_fixture():
    result = first_slice_viability(
        "runtime/cache.py:load_rows",
        {"side_effects": ["memory_state"]},
    )

    assert result["reselection_required"] is True
    assert any(row["rule_id"] == "stateful_runtime_function" for row in result["matched_rules"])


def test_unknown_parameter_object_protocol_requires_reselection():
    result = first_slice_viability(
        "orders.py:trigger",
        {
            "snippet": {
                "target_binding": "function_symbol",
                "text": "def trigger(order):\n    return order.set_strategy('trigger')",
            }
        },
    )

    assert result["status"] == "deferred"
    assert result["reselection_required"] is True
    assert any(
        row["rule_id"] == "unmaterialized_object_protocol_input"
        for row in result["matched_rules"]
    )


def test_common_scalar_protocol_remains_materializable():
    result = first_slice_viability(
        "text.py:normalize",
        {
            "snippet": {
                "target_binding": "function_symbol",
                "text": "def normalize(value):\n    return value.strip().lower()",
            }
        },
    )

    assert result["status"] == "eligible"
    assert result["reselection_required"] is False


def test_response_status_attribute_is_materializable():
    result = first_slice_viability(
        "client.py:validate_response",
        {
            "snippet": {
                "target_binding": "function_symbol",
                "text": "def validate_response(response):\n    return response.status_code == 200",
            }
        },
    )

    assert result["status"] == "eligible"
    assert result["reselection_required"] is False


def test_analyzer_response_protocol_uses_materializable_attributes():
    result = first_slice_viability(
        "client.py:validate_response",
        {
            "dependency_readiness": {"status": "missing_external"},
            "snippet": {
                "text": (
                    "def validate_response(response):\n"
                    "    if response.status_code == status.HTTP_404_NOT_FOUND:\n"
                    "        raise ValueError\n"
                    "    return status.is_client_error(code=response.status_code)"
                ),
                "structural_contract": {
                    "argument_usage_types": {"response": "ProtocolLike"},
                    "accessed_attributes": [
                        "HTTP_404_NOT_FOUND",
                        "is_client_error",
                        "status_code",
                    ],
                }
            },
        },
    )

    assert result["status"] == "eligible"
    assert result["reselection_required"] is False
    assert {row["rule_id"] for row in result["matched_rules"]} == {
        "bounded_transform_boundary",
        "unready_dependency_boundary",
    }


def test_composite_client_close_is_lifecycle_boundary():
    result = first_slice_viability("client.py:close_client")

    assert result["status"] == "deferred"
    assert result["reselection_required"] is True


def test_array_shape_access_remains_materializable():
    result = first_slice_viability(
        "features.py:extract_features",
        {
            "snippet": {
                "target_binding": "function_symbol",
                "text": "def extract_features(values):\n    return values.shape[-1]",
            }
        },
        knowledge_rule="scientific_compute_library",
    )

    assert result["status"] == "eligible"
    assert result["reselection_required"] is False


def test_analyzer_protocol_usage_survives_truncated_snippet():
    result = first_slice_viability(
        "metrics.py:build_payload",
        {
            "snippet": {
                "text": "def build_payload(config):\n    if config.metrics:\n        ...",
                "structural_contract": {
                    "argument_usage_types": {"config": "ProtocolLike"}
                },
            }
        },
    )

    assert result["status"] == "deferred"
    assert result["reselection_required"] is True


def test_declared_domain_model_remains_valid_architecture_target():
    result = first_slice_viability(
        "main.py:price_item",
        {
            "snippet": {
                "signature": {
                    "args": [{"name": "req", "annotation": "ItemRequest"}]
                },
                "structural_contract": {
                    "argument_usage_types": {"req": "ProtocolLike"}
                },
            }
        },
    )

    assert result["status"] == "eligible"
    assert result["reselection_required"] is False


def test_docstring_declared_dataframe_protocol_is_fixture_eligible():
    result = first_slice_viability(
        "datacleaner.py:autoclean_cv",
        {
            "dependency_readiness": {"status": "missing_external"},
            "snippet": {
                "structural_contract": {
                    "argument_usage_types": {
                        "training_dataframe": "ProtocolLike",
                        "testing_dataframe": "ProtocolLike",
                    },
                    "docstring_argument_types": {
                        "training_dataframe": "pandas.DataFrame",
                        "testing_dataframe": "pandas.DataFrame",
                    },
                },
            },
        },
    )

    assert result["status"] == "eligible"
    assert result["reselection_required"] is False
    assert {row["rule_id"] for row in result["matched_rules"]} == {
        "declared_protocol_input",
        "unready_dependency_boundary",
    }


def test_runtime_callback_requires_fixture_before_selection():
    result = first_slice_viability("main.py:sub_cb")

    assert result["status"] == "deferred"
    assert result["reselection_required"] is True


def test_vendored_tooling_is_not_a_project_owned_first_slice():
    result = first_slice_viability("ext_tools/makeheaders/makeheaders.py:export")

    assert result["status"] == "deferred"
    assert result["reselection_required"] is True

    private_vendor = first_slice_viability("package/_vendor/dataclasses.py:_get_field")
    assert private_vendor["status"] == "deferred"


def test_network_effect_and_private_hook_require_adapter_slice():
    network = first_slice_viability("client/api.py:add_photo", {"side_effects": ["network"]})
    hook = first_slice_viability("spinner.py:_hook")

    assert network["reselection_required"] is True
    assert hook["reselection_required"] is True


def test_architect_reselection_uses_kb_viability_order():
    sources = [
        "model/network.py:train",
        "dataset/io.py:get_batch",
        "dataset/io.py:normalize_batch",
    ]
    selected, evidence = _viable_candidates(
        sources,
        {},
        {"first_slice_contract": {"knowledge_rule": "scientific_compute_library"}},
        limit=8,
    )

    assert selected == ["dataset/io.py:normalize_batch", "dataset/io.py:get_batch"]
    assert [row["score"] for row in evidence] == [45, -70, 24]
    assert [row["target"] for row in evidence if row["viability_eligible"]] == selected


def test_architect_reselection_prefers_environment_ready_over_manifest_candidate():
    sources = ["pkg/heavy.py:normalize", "pkg/core.py:get_value"]
    context = {
        sources[0]: {
            "node_kind": "function",
            "snippet": {"text": "def normalize(value): ...", "target_binding": "function_symbol"},
            "dependency_readiness": {"status": "missing_external"},
        },
        sources[1]: {
            "node_kind": "function",
            "snippet": {"text": "def get_value(value): ...", "target_binding": "function_symbol"},
            "dependency_readiness": {"status": "ready"},
        },
    }

    selected, evidence = _viable_candidates(sources, context, {}, limit=8)

    assert selected == ["pkg/core.py:get_value", "pkg/heavy.py:normalize"]
    assert evidence[0]["environment_ready"] is True
    assert evidence[1]["environment_ready"] is False
