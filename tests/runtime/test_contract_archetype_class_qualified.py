from runtime.contract_archetype_inference import matching_archetypes
from runtime.role_spec_writer_ranking import name_and_contract_score
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


def test_pool_owner_disambiguates_resource_release_from_project_release():
    resource = matching_archetypes("facex/core.py:PoolManager.release_classifier")
    project = matching_archetypes("release.py:ReleaseManager.release_package")

    assert "object_pool_resource_release" in {row["id"] for row in resource}
    assert "object_pool_resource_release" not in {row["id"] for row in project}


def test_resource_release_method_is_not_treated_as_project_release_support():
    _, resource_reasons = name_and_contract_score(
        "facex/core.py:PoolManager.release_classifier",
        {"args": [{"name": "classifier", "annotation": "EmotionClassifier"}]},
        ["memory_state"],
    )
    _, project_reasons = name_and_contract_score(
        "release.py:release", {"args": []}, []
    )

    assert not any("release/build/publish support" in reason for reason in resource_reasons)
    assert any("release/build/publish support" in reason for reason in project_reasons)


def test_component_tree_projection_is_profiled_without_project_name():
    rows = matching_archetypes("pkg/output.py:add_component_items")

    assert "component_tree_projection" in {row["id"] for row in rows}
