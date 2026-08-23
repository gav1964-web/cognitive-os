import json

from runtime.improvement_plugins import candidate_selection_admission as admission


def _record(project, failed_basis, successful_basis):
    return {
        "contrast_id": "executable_sample_contract:measured_candidate_reselection",
        "_confirmed_projects": [project],
        "failed_contract": {
            "acceptance_signal": "meta_only",
            "return_paths": 1,
            "output_inference_basis": failed_basis,
        },
        "successful_contract": {
            "acceptance_signal": "executable_callable",
            "return_paths": 1,
            "output_inference_basis": successful_basis,
        },
    }


def _group(records):
    return {
        "id": "executable_sample_contract:measured_candidate_reselection",
        "records": records,
        "projects": {project for row in records for project in row["_confirmed_projects"]},
    }


def test_mixed_contrasts_form_only_homogeneous_structural_families():
    records = [
        _record("alpha", "insufficient_structural_evidence", "return_expression"),
        _record("beta", "insufficient_structural_evidence", "return_expression"),
        _record("gamma", "explicit_none_annotation", "explicit_return_annotation"),
        _record("delta", "return_expression", "return_expression"),
    ]

    families = admission._structural_families([_group(records)])

    insufficient = next(
        row for row in families
        if row["policy"]["structural_requirements"].get("forbidden_output_inference_basis")
        == ["insufficient_structural_evidence"]
    )
    assert insufficient["projects"] == {"alpha", "beta"}
    assert len(insufficient["records"]) == 2
    assert all(row["id"].count(":") == 2 for row in families)
    assert "delta" not in {project for row in families for project in row["projects"]}


def test_policy_family_signature_is_stable_across_record_order():
    first = _record("alpha", "insufficient_structural_evidence", "return_expression")
    second = _record("beta", "explicit_none_annotation", "explicit_return_annotation")

    forward = admission._structural_families([_group([first, second])])
    reverse = admission._structural_families([_group([second, first])])

    assert [row["id"] for row in forward] == [row["id"] for row in reverse]
    assert [
        json.dumps(row["policy"], sort_keys=True) for row in forward
    ] == [json.dumps(row["policy"], sort_keys=True) for row in reverse]


def test_uniform_group_preserves_original_policy_id():
    records = [
        _record(project, "insufficient_structural_evidence", "return_expression")
        for project in ("alpha", "beta", "gamma")
    ]

    families = admission._structural_families([_group(records)])

    assert len(families) == 1
    assert families[0]["id"] == "executable_sample_contract:measured_candidate_reselection"
    assert len(families[0]["projects"]) == 3


def test_policy_uses_minimal_discriminator_before_typed_count():
    row = _record("alpha", "explicit_none_annotation", "explicit_return_annotation")
    row["failed_contract"]["typed_argument_count"] = 0
    row["successful_contract"]["typed_argument_count"] = 2

    policy = admission._synthesize_policy({"id": "contrast", "records": [row]})

    assert "min_typed_argument_count" not in policy["structural_requirements"]
    assert policy["structural_requirements"]["forbidden_output_inference_basis"] == [
        "explicit_none_annotation",
    ]
