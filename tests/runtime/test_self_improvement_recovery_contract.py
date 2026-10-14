import json

from runtime.self_improvement_recovery_contract import recovery_contract


def test_recovery_contract_uses_successful_structural_side(tmp_path):
    path = tmp_path / "candidate.json"
    path.write_text(json.dumps({
        "record_type": "foundation_selection_contrast",
        "proposed_record": {"successful_contract": {
            "output_inference_basis": "return_expression",
            "return_paths": 2,
            "observed_side_effects": [],
            "state_mutation": False,
        }},
    }), encoding="utf-8")

    assert recovery_contract({"knowledge_candidate_path": str(path)}) == {
        "min_return_paths": 1,
        "forbidden_output_inference_basis": [
            "explicit_none_annotation", "insufficient_structural_evidence", "no_value_return",
        ],
        "no_observed_side_effects": True,
        "state_mutation": False,
    }
