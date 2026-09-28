from __future__ import annotations

from tests.runtime.first_slice_viability_helpers import *

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
    assert [row["target"] for row in evidence] == [
        "pkg/data.py:create_set", "pkg/model.py:extract",
    ]
    assert evidence[0]["receiver_independent"] is True
    assert evidence[1]["viability_eligible"] is False


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
        "no_semantically_safe_candidate_in_approved_first_slice",
    }
    assert state["spec"] is artifacts["technical_spec"]
