from runtime.first_slice_reselection_request import build_first_slice_reselection_request


def test_spec_writer_accepts_strong_candidate_at_policy_floor():
    contract = {
        "candidate": "pkg/core.py:screen_size",
        "semantic_quality": {"status": "strong", "score": 95},
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

    assert request["status"] == "not_required"


def test_spec_writer_returns_candidate_below_policy_floor_to_architect():
    contract = {
        "candidate": "pkg/core.py:screen_size",
        "semantic_quality": {"status": "strong", "score": 94},
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
    assert request["blocking_evidence"]["minimum_semantic_score"] == 95


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


def test_spec_writer_preserves_architect_semantic_viability_override():
    contract = {
        "candidate": "pkg/handlers.py:format_timestamp",
        "semantic_quality": {"status": "strong", "score": 89},
        "structural_evidence": {
            "argument_count": 1,
            "typed_argument_count": 0,
            "explicit_return_annotation": "",
        },
        "first_slice_viability": {
            "status": "eligible",
            "reselection_required": False,
            "matched_rules": [{"rule_id": "static_time_format_boundary"}],
        },
    }

    request = build_first_slice_reselection_request(
        contract,
        {"status": "not_required", "ranked_alternatives": []},
    )

    assert request["status"] == "not_required"
