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


def test_instance_and_static_methods_remain_eligible_for_ranked_selection():
    method = first_slice_viability(
        "utils/config.py:load",
        {"snippet": {"target_binding": "method_symbol", "owner_class": "Config", "text": "def load(self): return self.path"}},
    )
    static = first_slice_viability(
        "utils/config.py:load",
        {"snippet": {"target_binding": "method_symbol", "owner_class": "Config", "decorators": ["staticmethod"]}},
    )

    assert method["status"] == "eligible"
    assert method["reselection_required"] is False
    assert static["status"] == "eligible"


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


def test_architect_reselection_prefers_standalone_callable_over_instance_method():
    sources = ["pkg/model.py:extract", "pkg/data.py:create_set"]
    context = {
        sources[0]: {
            "node_kind": "function",
            "snippet": {"text": "def extract(self, value): return value", "target_binding": "method_symbol"},
            "dependency_readiness": {"status": "ready"},
        },
        sources[1]: {
            "node_kind": "function",
            "snippet": {"text": "def create_set(value): return value", "target_binding": "function_symbol"},
            "dependency_readiness": {"status": "ready"},
        },
    }

    selected, evidence = _viable_candidates(sources, context, {}, limit=8)

    assert selected == ["pkg/data.py:create_set", "pkg/model.py:extract"]
    assert evidence[0]["receiver_independent"] is True


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
    assert calls[0]["reselection_triggers"] == {"low_first_slice_viability"}
    assert state["spec"] is artifacts["technical_spec"]
