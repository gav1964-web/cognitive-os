import runtime.role_pipeline_stages as pipeline_stages

from runtime.architect_first_slice_reselection import _previous_primary_targets, _viable_candidates
from runtime.first_slice_reselection_request import build_first_slice_reselection_request
from runtime.first_slice_viability import first_slice_viability


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


def test_super_delegating_instance_method_still_requires_receiver_fixture():
    result = first_slice_viability(
        "pkg/widgets.py:PasswordEntry.show_line",
        {
            "snippet": {
                "text": "def show_line(self, value): return super().show_line(value)",
                "target_binding": "method_symbol",
            }
        },
    )

    assert result["status"] == "deferred"
    assert result["reselection_required"] is True


def test_runtime_lifecycle_and_cli_boundaries_require_cheaper_slice():
    lifecycle = first_slice_viability("runtime/worker.py:execute")
    cli = first_slice_viability("pkg/cli/base.py:list_templates")
    training = first_slice_viability("models/network.py:train_model")

    assert lifecycle["reselection_required"] is True
    assert cli["reselection_required"] is True
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
    assert [row["score"] for row in evidence] == [45, 24]


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


def test_architect_reselection_excludes_instance_method_that_requires_fixture():
    sources = ["pkg/model.py:extract", "pkg/data.py:create_set"]
    context = {
        sources[0]: {
            "node_kind": "function",
            "snippet": {"text": "def extract(self, value): return self.value + value", "target_binding": "method_symbol"},
            "dependency_readiness": {"status": "ready"},
        },
        sources[1]: {
            "node_kind": "function",
            "snippet": {"text": "def create_set(value): return value", "target_binding": "function_symbol"},
            "dependency_readiness": {"status": "ready"},
        },
    }

    selected, evidence = _viable_candidates(sources, context, {}, limit=8)

    assert selected == ["pkg/data.py:create_set"]
    assert [row["target"] for row in evidence] == ["pkg/data.py:create_set"]
    assert evidence[0]["receiver_independent"] is True


def test_architect_reselection_prefers_complete_contract_over_accessor():
    sources = ["pkg/fields.py:get_attribute", "pkg/fields.py:parse_data"]
    context = {
        sources[0]: {
            "node_kind": "function",
            "snippet": {
                "text": "def get_attribute(instance): return instance.value",
                "target_binding": "function_symbol",
                "signature": {"args": [{"name": "instance"}]},
                "structural_contract": {
                    "source_body_complete": True,
                    "argument_usage_types": {"instance": "ProtocolLike"},
                    "inferred_output_type": "AttributeValue",
                },
            },
            "dependency_readiness": {"status": "ready"},
        },
        sources[1]: {
            "node_kind": "function",
            "snippet": {
                "text": "def parse_data(data): return dict(data)",
                "target_binding": "function_symbol",
                "signature": {"args": [{"name": "data", "annotation": "MappingLike"}]},
                "structural_contract": {
                    "source_body_complete": True,
                    "argument_usage_types": {"data": "MappingLike"},
                    "inferred_output_type": "MappingLike",
                },
            },
            "dependency_readiness": {"status": "ready"},
        },
    }

    selected, evidence = _viable_candidates(sources, context, {}, limit=8)

    assert selected == ["pkg/fields.py:parse_data"]
    assert evidence[0]["semantic_score"] == 100


def test_static_dependency_tree_requires_project_owned_reselection():
    result = first_slice_viability(
        "pkg/_static_dependencies/ethereum/utils/module_loading.py:import_string"
    )

    assert result["reselection_required"] is True
    assert any(row["rule_id"] == "vendored_tooling_tree" for row in result["matched_rules"])


def test_architect_reselection_remembers_rejected_primary_targets():
    decision = {
        "first_slice_reselection_history": [
            {"selected_targets": ["pkg/core.py:first", "pkg/core.py:context"]},
            {"selected_targets": ["pkg/core.py:second"]},
        ]
    }

    assert _previous_primary_targets(decision) == {
        "pkg/core.py:first",
        "pkg/core.py:second",
    }


def test_spec_writer_returns_deferred_candidate_to_architect():
    contract = {
        "candidate": "model/network.py:predict",
        "first_slice_viability": {"status": "deferred", "reselection_required": True, "score": -70},
    }

    request = build_first_slice_reselection_request(
        contract,
        {"status": "not_required", "ranked_alternatives": []},
    )

    assert request["status"] == "required"
    assert request["trigger"] == "low_first_slice_viability"
    assert request["blocking_evidence"]["first_slice_viability"]["score"] == -70


def test_production_build_stage_runs_configured_reselection_loop(monkeypatch, tmp_path):
    artifacts = {
        "architecture_decision": {"artifact_type": "ArchitectureDecisionRecord"},
        "technical_spec": {"artifact_type": "TechnicalSpec"},
        "implementation_plan": {"artifact_type": "ImplementationPlan"},
        "test_plan": {"artifact_type": "TestPlan"},
        "programmer_task_tree": {"artifact_type": "ProgrammerTaskTree"},
    }
    calls = []

    def run_prefix(**kwargs):
        calls.append(kwargs)
        return artifacts

    monkeypatch.setattr(pipeline_stages, "run_configured_role_prefix", run_prefix)
    state = {
        "root": tmp_path,
        "project_dir": tmp_path,
        "goal": "Select an executable slice",
        "project_report": {},
        "architect_advisory_config": None,
        "run_executor": True,
        "write": False,
    }

    pipeline_stages.stage_build(state)

    assert calls[0]["until_output_key"] == "programmer_task_tree"
    assert calls[0]["reselection_triggers"] == {
        "low_first_slice_viability",
        "first_slice_semantic_quality_below_threshold",
    }
    assert state["spec"] is artifacts["technical_spec"]
