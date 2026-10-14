from runtime.self_improvement_experience import _portable_contract


def test_portable_contract_keeps_materialization_and_execution_cost_facts():
    contract = _portable_contract({
        "selected_candidate_quality": {
            "structural_evidence": {
                "argument_count": 1,
                "argument_usage_types": {"value": "ArrayLike"},
                "return_paths": 1,
            },
            "selection_evidence": {
                "ranking_reasons": [
                    "execution cost requires reselection: instance_method_receiver, runtime_global"
                ],
                "dependency_readiness": {"status": "ready"},
            },
        },
        "downstream_evidence": {"acceptance_signal": "meta_only"},
    })

    assert contract["argument_shape_families"] == ["ArrayLike"]
    assert contract["execution_cost_rules"] == ["instance_method_receiver", "runtime_global"]
    assert contract["dependency_status"] == "ready"
