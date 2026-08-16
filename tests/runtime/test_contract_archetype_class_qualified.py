from runtime.contract_archetype_inference import matching_archetypes
from runtime.target_quality import semantic_target_quality_report


def test_class_owner_name_does_not_trigger_method_contract_archetype():
    target = "rest_pandas/renderers.py:PandasBaseRenderer.get_pandas_args"

    matches = matching_archetypes(target)

    assert "interactive_application_run_loop" not in {row["id"] for row in matches}


def test_request_parameter_projection_has_bounded_contract_family():
    target = "sdk/rest/base.py:_get_params"

    report = semantic_target_quality_report(
        target,
        ranked_candidates=[target],
        source_evidence=[target],
        input_contract={"caller_values": "MappingLike"},
        output_contract={"query_params": "MappingLike"},
    )

    assert report["profiled_contract_family"] is True
    assert "request_parameter_projection" in report["contract_archetype_ids"]
    assert report["score"] >= 90
