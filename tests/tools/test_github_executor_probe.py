from tools import github_executor_probe
from tools.github_executor_probe import _boundary_track, _run_case, _strategy_fields, _summary, _task_tree_fields
from tools.github_implementer_probe import _quality_score


def test_summary_counts_executor_acceptance_and_source_changes() -> None:
    cases = [
        {
            "status": "ok",
            "executor_status": "ok",
            "executable_acceptance": "passed",
            "acceptance_signal": "executable_callable",
            "effect_module_stub_targets": {"pkg/net.py:is_open": ["socket"]},
            "boundary_track": "pure_python_callable",
            "dependency_readiness_status": "missing_external",
            "dependency_missing_modules": ["optional_sdk"],
            "dependency_profile_status": "resolution_required",
            "task_tree_status": "ready",
            "task_tree_boundary": "sandbox_patch_tree",
            "task_tree_node_count": 5,
            "patch_synthesis": "prepared",
            "patch_quality_level": "signature_fallback_guard",
            "patch_quality_review_required": True,
            "strategy_action": "verify_patch",
            "contract_rebind_requested": True,
            "contract_rebind_reason": "nested_closure_target",
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
        "acceptance_effect_stubbed": 1,
        "effect_stub_modules": {"socket": 1},
        "boundary_tracks": {"blocked_handoff": 1, "pure_python_callable": 1, "unknown": 1},
        "contract_profiles": {"none": 3},
        "contract_profile_operators": {"none": 3},
        "dependency_readiness_statuses": {"missing_external": 1, "unknown": 2},
        "dependency_missing_modules": {"optional_sdk": 1},
        "dependency_profile_statuses": {"none": 2, "resolution_required": 1},
        "task_tree_statuses": {"needs_review": 1, "ready": 1, "unknown": 1},
        "task_tree_boundaries": {"blocked_handoff": 1, "sandbox_patch_tree": 1, "unknown": 1},
        "task_tree_dependency_edges_total": 0,
        "task_tree_unmapped_acceptance_total": 0,
        "task_tree_changes_traced": 0,
        "strategy_actions": {"unknown": 2, "verify_patch": 1},
        "contract_rebind_requested": 1,
        "contract_rebind_reasons": {"nested_closure_target": 1},
        "executor_playbooks": {"executor_playbook_callable_acceptance_verify": 1},
        "solution_patterns": {"executor_pattern_blocked_handoff": 1, "executor_pattern_signature_fallback_review": 1},
        "llm_strategy_statuses": {"none": 2, "not_requested": 1},
        "sandbox_candidate_statuses": {"none": 2, "not_available": 1},
        "sandbox_candidate_attempt_statuses": {"none": 2, "not_attempted": 1},
        "sandbox_candidate_repair_statuses": {"none": 2, "not_attempted": 1},
        "source_code_changes": 1,
    }


def test_strategy_fields_exposes_contract_rebind_evidence() -> None:
    fields = _strategy_fields(
        {
            "contract_rebind_request": {
                "reason": "test_plan_target_drift",
                "candidate_targets": [{"target": "pkg/other.py:build"}],
            }
        }
    )

    assert fields["contract_rebind_requested"] is True
    assert fields["contract_rebind_reason"] == "test_plan_target_drift"
    assert fields["contract_rebind_candidates"] == ["pkg/other.py:build"]


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


def test_case_isolates_foreign_argparse_system_exit(tmp_path, monkeypatch) -> None:
    project = tmp_path / "foreign_cli"
    project.mkdir()
    monkeypatch.setattr(github_executor_probe, "_git_porcelain", lambda _path: "")
    monkeypatch.setattr(github_executor_probe, "analyze_project", lambda _path: (_ for _ in ()).throw(SystemExit(2)))

    result = _run_case(root=tmp_path, project_dir=project, run_verification=False)

    assert result["status"] == "failed"
    assert result["error"] == "SystemExit: 2"


def test_task_tree_fields_expose_quality_evidence() -> None:
    fields = _task_tree_fields(
        {
            "status": "ready",
            "boundary": {"track": "sandbox_patch_tree"},
            "summary": {"node_count": 8, "change_node_count": 3, "acceptance_node_count": 2, "dependency_edge_count": 9},
            "coverage": {"unmapped_acceptance_ids": [], "all_changes_traced": True},
        }
    )

    assert fields["task_tree_dependency_edge_count"] == 9
    assert fields["task_tree_unmapped_acceptance_count"] == 0
    assert fields["task_tree_all_changes_traced"] is True


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
