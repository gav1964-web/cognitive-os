from runtime.semantic_target_profiles import (
    contract_for_target,
    semantic_ranking_adjustments,
    semantic_score_adjustments,
)


def test_biological_sequence_design_has_a_profiled_contract():
    target = "proteinsolver/utils/protein_design.py:design_sequence"

    contract = contract_for_target(target)

    assert contract["contract_family"] == "biological_sequence_design_boundary"
    assert "sequence_graph" in contract["input_contract"]
    assert semantic_score_adjustments(target)["score_delta"] == 24
    assert semantic_ranking_adjustments(target)["score_delta"] == 52
