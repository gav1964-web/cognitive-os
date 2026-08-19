from runtime.first_slice_reselection_request import build_first_slice_reselection_request


def test_spec_writer_returns_low_quality_strong_candidate_to_architect():
    contract = {
        "candidate": "pkg/core.py:screen_size",
        "semantic_quality": {"status": "strong", "score": 96},
        "structural_evidence": {
            "argument_count": 0,
            "typed_argument_count": 0,
            "explicit_return_annotation": "",
        },
        "first_slice_viability": {"status": "eligible", "reselection_required": False},
    }

    request = build_first_slice_reselection_request(
        contract,
        {"status": "not_required", "ranked_alternatives": []},
    )

    assert request["status"] == "required"
    assert request["trigger"] == "first_slice_semantic_quality_below_threshold"
    assert request["blocking_evidence"]["minimum_semantic_score"] == 97


def test_fully_annotated_contract_does_not_reselect_for_missing_docstring_points():
    contract = {
        "candidate": "pkg/core.py:normalize",
        "semantic_quality": {"status": "strong", "score": 96},
        "structural_evidence": {
            "argument_count": 1,
            "typed_argument_count": 1,
            "explicit_return_annotation": "str",
        },
        "first_slice_viability": {"status": "eligible", "reselection_required": False},
    }

    request = build_first_slice_reselection_request(
        contract,
        {"status": "not_required", "ranked_alternatives": []},
    )

    assert request["status"] == "not_required"


def test_spec_writer_returns_deferred_candidate_without_explicit_rule_flag():
    contract = {
        "candidate": "pkg/core.py:load_data",
        "semantic_quality": {"status": "strong", "score": 100},
        "first_slice_viability": {"status": "deferred", "reselection_required": False},
    }

    request = build_first_slice_reselection_request(
        contract,
        {"status": "not_required", "ranked_alternatives": []},
    )

    assert request["status"] == "required"
    assert request["trigger"] == "low_first_slice_viability"
