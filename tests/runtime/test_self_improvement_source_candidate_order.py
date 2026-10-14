from runtime.self_improvement_failure_evidence import _source_candidate_pool


def _row(*, binding: str, dependency: str):
    return {
        "target_binding": binding,
        "dependency_readiness": {"status": dependency},
        "structural_contract": {
            "return_paths": 1,
            "output_inference_basis": "return_expression",
            "observed_side_effects": [],
        },
    }


def test_top_level_function_precedes_ready_receiver_method_in_recovery_pool():
    context = {
        "admin.py:Admin.has_permission": _row(
            binding="method_symbol", dependency="ready"
        ),
        "helpers.py:normalize_user": _row(
            binding="function_symbol", dependency="missing_external"
        ),
    }

    assert _source_candidate_pool(context)[0] == "helpers.py:normalize_user"
