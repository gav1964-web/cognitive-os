from runtime.selected_candidate_quality import selected_candidate_quality


def test_selected_quality_preserves_ranked_execution_evidence():
    spec = {
        "source_evidence": [{"source": "app.py:parse"}],
        "extraction_contract": {
            "candidate": "app.py:parse",
            "selection_reason": "bounded candidate",
            "structural_evidence": {"argument_count": 1, "return_paths": 1},
            "input_contract": {"value": "str"},
            "output_contract": {"result": "str"},
            "side_effects": {"declared": []},
            "ranked_candidates": [{
                "source": "app.py:parse",
                "kind": "function",
                "score": 61,
                "reasons": [
                    "execution cost requires reselection: method_runtime_global_dependency"
                ],
                "dependency_readiness": {"status": "ready"},
            }],
        },
    }

    quality = selected_candidate_quality(spec)

    assert quality["selection_evidence"] == {
        "ranked_score": 61,
        "kind": "function",
        "ranking_reasons": [
            "execution cost requires reselection: method_runtime_global_dependency"
        ],
        "dependency_readiness": {"status": "ready"},
    }
