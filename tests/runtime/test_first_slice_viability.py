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
