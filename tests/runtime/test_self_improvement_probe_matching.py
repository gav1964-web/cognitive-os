from runtime.self_improvement_hypothesis_validation import _probe_matches


def test_probe_recovers_missing_diagnosis_class_from_portable_signature():
    probe = {
        "baseline": {
            "downstream_evidence": {"reason": "side_effectful_target"},
            "selected_candidate_quality": {
                "structural_evidence": {
                    "observed_side_effects": ["memory_state"],
                    "output_inference_basis": "explicit_none_annotation",
                }
            },
        },
        "diagnosis": {},
    }
    plan = {
        "failure_class": "side_effectful_target",
        "portable_signature": "side_effectful_target|memory_state|void_side_effect",
        "signature_normalization": {
            "output_basis_families": {
                "void_side_effect": [
                    "no_value_return", "explicit_none_annotation",
                ]
            }
        },
    }

    assert _probe_matches(probe, plan)
