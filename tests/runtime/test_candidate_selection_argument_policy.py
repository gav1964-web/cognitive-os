import json

from runtime.promoted_candidate_selection_policies import (
    apply_preflight_selection_policies,
    apply_selection_policies,
)


def test_execution_feedback_not_measured_signal_uses_meta_only_policy(tmp_path):
    path = tmp_path / "policies.json"
    path.write_text(json.dumps({
        "schema_version": "promoted_candidate_selection_policies.v1",
        "policies": [{
            "id": "returning_challenger",
            "activation_state": "active",
            "trigger": "executable_acceptance_rejected",
            "trigger_signals": ["meta_only"],
            "structural_requirements": {"min_return_paths": 1},
            "numeric_bonus": False,
        }],
    }), encoding="utf-8")
    ranked = [{"target": "write", "return_paths": 0}, {"target": "build", "return_paths": 1}]

    result = apply_selection_policies(
        ranked,
        {"trigger": "executable_acceptance_rejected", "blocking_evidence": {
            "acceptance_signal": "not_measured",
        }},
        path=str(path),
    )

    assert [row["target"] for row in result] == ["build", "write"]


def test_execution_feedback_requires_preflight_match_for_trigger_candidate(tmp_path):
    path = tmp_path / "policies.json"
    path.write_text(json.dumps({
        "schema_version": "promoted_candidate_selection_policies.v1",
        "policies": [{
            "id": "missing_dependency_reselection",
            "activation_state": "active",
            "trigger": "executable_acceptance_rejected",
            "trigger_signals": ["meta_only"],
            "preflight_trigger_requirements": {"dependency_status": ["missing_external"]},
            "structural_requirements": {"max_argument_count": 1},
            "numeric_bonus": False,
        }],
    }), encoding="utf-8")
    ranked = [{"target": "fallback", "argument_count": 1}]
    request = {
        "trigger": "executable_acceptance_rejected",
        "trigger_candidate": {"dependency_readiness": {"status": "ready"}},
    }

    assert apply_selection_policies(ranked, request, path=str(path)) == ranked


def test_active_policy_preflight_prefers_bounded_argument_contract(tmp_path):
    policy_path = tmp_path / "policies.json"
    policy_path.write_text(json.dumps({
        "schema_version": "promoted_candidate_selection_policies.v1",
        "policies": [{
            "id": "bounded_arguments",
            "activation_state": "active",
            "trigger": "executable_acceptance_rejected",
            "trigger_signals": ["meta_only"],
            "selection_mode": "stable_partition_existing_candidates",
            "preflight_trigger_requirements": {"min_argument_count": 2},
            "structural_requirements": {"max_argument_count": 1},
            "numeric_bonus": False,
        }],
    }), encoding="utf-8")
    ranked = [
        {"source": "complex", "evidence": {"structural_contract": {"argument_count": 3}}},
        {"source": "bounded", "evidence": {"structural_contract": {"argument_count": 1}}},
    ]

    reordered = apply_preflight_selection_policies(ranked, path=str(policy_path))

    assert [row["source"] for row in reordered] == ["bounded", "complex"]


def test_preflight_execution_cost_policy_excludes_matching_candidate(tmp_path):
    policy_path = tmp_path / "policies.json"
    policy_path.write_text(json.dumps({
        "schema_version": "promoted_candidate_selection_policies.v1",
        "policies": [{
            "id": "runtime_cost",
            "activation_state": "active",
            "trigger": "executable_acceptance_rejected",
            "trigger_signals": ["meta_only"],
            "selection_mode": "stable_partition_existing_candidates",
            "preflight_trigger_requirements": {
                "any_ranking_reason_tokens": ["runtime_global"],
            },
            "structural_requirements": {
                "forbidden_ranking_reason_tokens": ["runtime_global"],
            },
            "numeric_bonus": False,
        }],
    }), encoding="utf-8")
    ranked = [
        {"source": "costly", "reasons": ["execution cost: runtime_global"]},
        {"source": "bounded", "reasons": ["source-backed transform"]},
    ]

    reordered = apply_preflight_selection_policies(ranked, path=str(policy_path))

    assert [row["source"] for row in reordered] == ["bounded", "costly"]


def test_preflight_policy_accepts_independent_risk_alternatives(tmp_path):
    policy_path = tmp_path / "policies.json"
    policy_path.write_text(json.dumps({
        "schema_version": "promoted_candidate_selection_policies.v1",
        "policies": [{
            "id": "learned_risks",
            "activation_state": "active",
            "trigger": "executable_acceptance_rejected",
            "trigger_signals": ["meta_only"],
            "selection_mode": "stable_partition_existing_candidates",
            "preflight_trigger_requirements": {"alternatives": [
                {"any_ranking_reason_tokens": ["runtime_global"]},
                {"output_inference_basis": ["module_side_effect_execution"]},
            ]},
            "structural_requirements": {"min_return_paths": 1},
            "numeric_bonus": False,
        }],
    }), encoding="utf-8")
    ranked = [
        {"source": "module", "evidence": {"structural_contract": {
            "return_paths": 0,
            "output_inference_basis": "module_side_effect_execution",
        }}},
        {"source": "callable", "evidence": {"structural_contract": {
            "return_paths": 1,
            "output_inference_basis": "return_expression",
        }}},
    ]

    reordered = apply_preflight_selection_policies(ranked, path=str(policy_path))

    assert [row["source"] for row in reordered] == ["callable", "module"]


def test_preflight_policy_uses_structured_dependency_status(tmp_path):
    policy_path = tmp_path / "policies.json"
    policy_path.write_text(json.dumps({
        "schema_version": "promoted_candidate_selection_policies.v1",
        "policies": [{
            "id": "dependency_readiness",
            "activation_state": "active",
            "trigger": "executable_acceptance_rejected",
            "trigger_signals": ["meta_only"],
            "selection_mode": "stable_partition_existing_candidates",
            "preflight_trigger_requirements": {
                "dependency_status": ["missing_external"],
            },
            "structural_requirements": {
                "forbidden_dependency_status": ["missing_external"],
            },
            "numeric_bonus": False,
        }],
    }), encoding="utf-8")
    ranked = [
        {"source": "blocked", "dependency_readiness": {"status": "missing_external"}},
        {"source": "ready", "dependency_readiness": {"status": "ready"}},
    ]

    reordered = apply_preflight_selection_policies(ranked, path=str(policy_path))

    assert [row["source"] for row in reordered] == ["ready", "blocked"]


def test_preflight_can_use_scoped_trigger_for_full_candidate_pool(tmp_path):
    policy_path = tmp_path / "policies.json"
    policy_path.write_text(json.dumps({
        "schema_version": "promoted_candidate_selection_policies.v1",
        "policies": [{
            "id": "scoped_trigger",
            "activation_state": "active",
            "trigger": "executable_acceptance_rejected",
            "trigger_signals": ["meta_only"],
            "selection_mode": "stable_partition_existing_candidates",
            "preflight_trigger_requirements": {"min_argument_count": 2},
            "structural_requirements": {"max_argument_count": 1},
            "numeric_bonus": False,
        }],
    }), encoding="utf-8")
    pool = [
        {"source": "unrelated", "evidence": {"structural_contract": {"argument_count": 0}}},
        {"source": "challenger", "evidence": {"structural_contract": {"argument_count": 1}}},
    ]
    scoped = {"source": "failed", "evidence": {"structural_contract": {"argument_count": 4}}}

    reordered = apply_preflight_selection_policies(
        pool, path=str(policy_path), trigger_candidate=scoped,
    )

    assert reordered[0]["source"] == "unrelated"
    assert reordered[0]["selection_policy_ids"] == ["scoped_trigger"]
