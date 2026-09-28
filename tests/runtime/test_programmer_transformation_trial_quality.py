from runtime.programmer_transformation_trial_quality import (
    evaluate_transformation_case,
    transformation_summary,
)


def _passing_case() -> dict:
    return evaluate_transformation_case(
        expected_profile="normalize_string",
        expected_operator="strip_lower",
        source_before="def normalize(value):\n    return value\n",
        source_after="def normalize(value):\n    return value\n",
        technical_spec={
            "implementation_delta": {
                "status": "ready",
                "intent": {"operator_id": "strip_lower"},
            },
            "extraction_contract": {
                "contract_profile": {"id": "normalize_string", "operator_id": "strip_lower"},
            },
        },
        result={"status": "ok", "source_code_changes": False},
        patch_package={
            "patch_synthesis": {"status": "prepared", "reason": "contract_transform_profile"},
            "patches": [{"target": "main.py:normalize", "transform": "strip_lower"}],
        },
        test_result={"executable_acceptance_result": {"status": "passed"}},
    )


def test_transformation_case_requires_every_invariant() -> None:
    case = _passing_case()

    assert case["status"] == "ok"
    assert case["score"] == 10.0
    assert set(case["checks"].values()) == {True}


def test_transformation_case_exposes_wrong_operator_as_minimum_loss() -> None:
    case = _passing_case()
    case["status"] = "needs_review"
    case["score"] = 8.89
    other = {**_passing_case(), "project": "b"}
    case["project"] = "a"

    summary = transformation_summary([other, case])

    assert summary["minimum_score"] == 8.89
    assert summary["accepted"] == 1
    assert summary["needs_review"] == 1
