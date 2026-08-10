from tools.github_executor_probe import _boundary_track, _summary
from tools.github_implementer_probe import _quality_score


def test_summary_counts_executor_acceptance_and_source_changes() -> None:
    cases = [
        {
            "status": "ok",
            "executor_status": "ok",
            "executable_acceptance": "passed",
            "acceptance_signal": "executable_callable",
            "boundary_track": "pure_python_callable",
            "task_tree_status": "ready",
            "task_tree_boundary": "sandbox_patch_tree",
            "task_tree_node_count": 5,
            "patch_synthesis": "prepared",
            "patch_quality_level": "signature_fallback_guard",
            "patch_quality_review_required": True,
            "strategy_action": "verify_patch",
            "executor_playbook_ids": ["executor_playbook_callable_acceptance_verify"],
            "solution_pattern_ids": ["executor_pattern_signature_fallback_review"],
            "llm_strategy_status": "not_requested",
            "sandbox_candidate_status": "not_available",
            "sandbox_candidate_attempt_status": "not_attempted",
            "sandbox_candidate_repair_status": "not_attempted",
            "source_code_changes": False,
        },
        {
            "status": "blocked_ok",
            "executor_status": "blocked",
            "executable_acceptance": None,
            "acceptance_signal": "blocked",
            "boundary_track": "blocked_handoff",
            "task_tree_status": "needs_review",
            "task_tree_boundary": "blocked_handoff",
            "task_tree_node_count": 5,
            "patch_synthesis": "blocked",
            "patch_quality_level": "blocked_handoff",
            "patch_quality_review_required": False,
            "solution_pattern_ids": ["executor_pattern_blocked_handoff"],
            "strategy_action": "",
            "llm_strategy_status": "",
            "sandbox_candidate_status": "",
            "source_code_changes": True,
        },
        {"status": "failed", "source_code_changes": False},
    ]

    assert _summary(cases) == {
        "ok": 1,
        "blocked_no_safe_candidate": 1,
        "accepted": 2,
        "needs_review": 0,
        "failed": 1,
        "executor_ok": 1,
        "executor_blocked": 1,
        "executable_acceptance_passed": 1,
        "patch_prepared": 1,
        "patch_blocked": 1,
        "patch_skipped": 0,
        "patch_quality_levels": {"blocked_handoff": 1, "none": 1, "signature_fallback_guard": 1},
        "patch_quality_review_required": 1,
        "acceptance_callable": 1,
        "acceptance_meta_only": 0,
        "boundary_tracks": {"blocked_handoff": 1, "pure_python_callable": 1, "unknown": 1},
        "contract_profiles": {"none": 3},
        "contract_profile_operators": {"none": 3},
        "task_tree_statuses": {"needs_review": 1, "ready": 1, "unknown": 1},
        "task_tree_boundaries": {"blocked_handoff": 1, "sandbox_patch_tree": 1, "unknown": 1},
        "strategy_actions": {"unknown": 2, "verify_patch": 1},
        "executor_playbooks": {"executor_playbook_callable_acceptance_verify": 1},
        "solution_patterns": {"executor_pattern_blocked_handoff": 1, "executor_pattern_signature_fallback_review": 1},
        "llm_strategy_statuses": {"none": 2, "not_requested": 1},
        "sandbox_candidate_statuses": {"none": 2, "not_available": 1},
        "sandbox_candidate_attempt_statuses": {"none": 2, "not_attempted": 1},
        "sandbox_candidate_repair_statuses": {"none": 2, "not_attempted": 1},
        "source_code_changes": 1,
    }


def test_boundary_track_classifies_native_optional_and_fixture_boundaries() -> None:
    assert _boundary_track({"signal_strength": "executable_callable"}) == "pure_python_callable"
    assert (
        _boundary_track(
            {
                "signal_strength": "meta_only",
                "skipped_reason_counts": {"import_failed_import_error": 1},
                "skipped_targets": [{"detail": "cryptography.hazmat.bindings._rust"}],
            }
        )
        == "native_extension_boundary"
    )
    assert _boundary_track({"signal_strength": "meta_only", "skipped_reason_counts": {"import_failed_missing_module": 1}}) == "optional_dependency_boundary"
    assert _boundary_track({"signal_strength": "meta_only", "skipped_reason_counts": {"positive_sample_execution_failed": 1}}) == "fixture_or_runtime_shape_boundary"


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
