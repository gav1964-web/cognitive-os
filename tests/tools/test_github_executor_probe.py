from tools.github_executor_probe import _summary
from tools.github_implementer_probe import _quality_score


def test_summary_counts_executor_acceptance_and_source_changes() -> None:
    cases = [
        {
            "status": "ok",
            "executor_status": "ok",
            "executable_acceptance": "passed",
            "acceptance_signal": "executable_callable",
            "patch_synthesis": "prepared",
            "source_code_changes": False,
        },
        {
            "status": "needs_review",
            "executor_status": "needs_review",
            "executable_acceptance": "failed",
            "acceptance_signal": "meta_only",
            "patch_synthesis": "skipped",
            "source_code_changes": True,
        },
        {"status": "failed", "source_code_changes": False},
    ]

    assert _summary(cases) == {
        "ok": 1,
        "needs_review": 1,
        "failed": 1,
        "executor_ok": 1,
        "executable_acceptance_passed": 1,
        "patch_prepared": 1,
        "patch_skipped": 1,
        "acceptance_callable": 1,
        "acceptance_meta_only": 1,
        "source_code_changes": 1,
    }


def test_implementer_probe_accepts_zero_arg_input_contract() -> None:
    score = _quality_score(
        {"extraction_contract": {"candidate": "pkg/core.py:contents"}},
        {
            "artifact_type": "ImplementationPlan",
            "role": "implementer",
            "expected_files": ["pkg/core.py"],
            "rollback_plan": {"registry_policy": "do not edit registry"},
            "verification_commands": ["python -m pytest -q"],
        },
        "pkg/core.py:contents",
        {
            "binding_status": "bound_to_extraction_contract",
            "input_contract": {},
            "output_contract": {"resource_value": "str"},
        },
        [],
        ["pkg/core.py:contents"],
        ["pkg/core.py:contents"],
    )

    assert score == 1.0
