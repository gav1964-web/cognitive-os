import json

from runtime.promoted_candidate_selection_policies import apply_preflight_selection_policies


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
