from __future__ import annotations

import json

from tools.field_trial_matrix import build_matrix, summary_view


def test_field_trial_matrix_counts_patch_reasons_and_failed_checks(tmp_path):
    report = {
        "cases": [
            {
                "project": "a",
                "status": "ok",
                "quality_score": 1.0,
                "target_chain": {"implementation_target": "a.py:run"},
                "executor": {
                    "patch_synthesis_status": "prepared",
                    "patch_synthesis_reason": "required_input_guard_synthesized",
                    "strategy_action": "verify_patch",
                    "strategy_reason": "deterministic_patch_ready",
                    "executor_playbook_ids": ["executor_playbook_callable_acceptance_verify"],
                    "task_tree_status": "ready",
                    "task_tree_boundary": "sandbox_patch_tree",
                    "task_tree_node_count": 5,
                    "llm_strategy_status": "not_requested",
                    "sandbox_candidate_status": "none",
                    "sandbox_candidate_attempt_status": "not_attempted",
                    "sandbox_candidate_repair_status": "not_attempted",
                    "acceptance_signal": "executable_callable",
                    "acceptance_skipped_reasons": {},
                    "callable_harness_count": 1,
                },
                "failed_checks": [],
            },
            {
                "project": "b",
                "status": "needs_review",
                "quality_score": 0.8,
                "target_chain": {"implementation_target": "b.py:run"},
                "executor": {
                    "patch_synthesis_status": "skipped",
                    "patch_synthesis_reason": "no_supported_patch_pattern",
                    "strategy_action": "ask_l45_for_patch_recipe_hypothesis",
                    "strategy_reason": "unsupported_pattern_needs_advisory_recipe",
                    "executor_playbook_ids": ["executor_playbook_dependency_boundary_profile"],
                    "task_tree_status": "needs_review",
                    "task_tree_boundary": "blocked_handoff",
                    "task_tree_node_count": 5,
                    "llm_strategy_status": "hypothesis_only",
                    "sandbox_candidate_status": "candidate_ready_for_sandbox_attempt",
                    "sandbox_candidate_attempt_status": "applied_in_sandbox",
                    "sandbox_candidate_repair_status": "applied_in_sandbox",
                    "acceptance_signal": "meta_only",
                    "acceptance_skipped_reasons": {"import_failed": 1},
                    "acceptance_skipped_targets": [
                        {
                            "target": "b.py:run",
                            "reason": "import_failed",
                            "detail": "missing_lib: No module named 'missing_lib'",
                        }
                    ],
                    "callable_harness_count": 0,
                },
                "failed_checks": [{"code": "tester_covers_contract"}],
            },
        ]
    }
    path = tmp_path / "report.json"
    path.write_text(json.dumps(report), encoding="utf-8")

    matrix = build_matrix(path)

    assert matrix["summary"]["status_counts"] == {"needs_review": 1, "ok": 1}
    assert matrix["summary"]["acceptance_signals"] == {"executable_callable": 1, "meta_only": 1}
    assert matrix["summary"]["acceptance_skipped_reasons"] == {"import_failed": 1}
    assert matrix["summary"]["acceptance_skipped_details"] == {"missing_lib: No module named 'missing_lib'": 1}
    assert matrix["summary"]["patch_reasons"]["no_supported_patch_pattern"] == 1
    assert matrix["summary"]["task_tree_statuses"] == {"needs_review": 1, "ready": 1}
    assert matrix["summary"]["task_tree_boundaries"] == {"blocked_handoff": 1, "sandbox_patch_tree": 1}
    assert matrix["summary"]["strategy_actions"] == {
        "ask_l45_for_patch_recipe_hypothesis": 1,
        "verify_patch": 1,
    }
    assert matrix["summary"]["executor_playbooks"] == {
        "executor_playbook_callable_acceptance_verify": 1,
        "executor_playbook_dependency_boundary_profile": 1,
    }
    assert matrix["summary"]["llm_strategy_statuses"] == {"hypothesis_only": 1, "not_requested": 1}
    assert matrix["summary"]["sandbox_candidate_statuses"] == {"candidate_ready_for_sandbox_attempt": 1, "none": 1}
    assert matrix["summary"]["sandbox_candidate_attempt_statuses"] == {"applied_in_sandbox": 1, "not_attempted": 1}
    assert matrix["summary"]["sandbox_candidate_repair_statuses"] == {"applied_in_sandbox": 1, "not_attempted": 1}
    assert matrix["summary"]["failed_checks"] == {"tester_covers_contract": 1}


def test_field_trial_matrix_summarizes_foundation_role_reports(tmp_path):
    report = {
        "artifact_type": "RoleFoundationFieldTrialReport",
        "target_score": 9.5,
        "cases": [
            {
                "project": "profiled",
                "status": "ok",
                "project_min_score": 9.8,
                "role_scores": {"project_analyzer": 10.0, "architect": 10.0, "spec_writer": 9.8},
                "selected_extraction_candidate": "pkg/jobs.py:acquire_jobs",
                "selected_candidate_quality": {
                    "score": 98,
                    "status": "strong",
                    "profiled_contract_family": True,
                    "semantic_profile_ids": ["scheduled_job_acquisition_boundary"],
                },
                "warnings": [],
            },
            {
                "project": "gap",
                "status": "ok",
                "project_min_score": 7.6,
                "role_scores": {"project_analyzer": 10.0, "architect": 10.0, "spec_writer": 7.6},
                "selected_extraction_candidate": "pkg/core.py:shape_only",
                "selected_candidate_quality": {"score": 76, "status": "acceptable", "profiled_contract_family": False},
                "warnings": [],
            },
            {
                "project": "shape_high",
                "status": "ok",
                "project_min_score": 10.0,
                "role_scores": {"project_analyzer": 10.0, "architect": 10.0, "spec_writer": 10.0},
                "selected_extraction_candidate": "pkg/schema.py:create_fields",
                "selected_candidate_quality": {"score": 100, "status": "strong", "profiled_contract_family": False},
                "warnings": [],
            },
            {
                "project": "native",
                "status": "out_of_scope",
                "blocker": "unsupported_primary_language_for_python_foundation",
                "role_scores": {"project_analyzer": None, "architect": None, "spec_writer": None},
                "selected_candidate_quality": {},
                "warnings": ["unsupported_primary_language_for_python_foundation"],
            },
        ],
    }
    path = tmp_path / "foundation.json"
    path.write_text(json.dumps(report), encoding="utf-8")

    matrix = build_matrix(path)

    assert matrix["artifact_type"] == "FoundationFieldTrialMatrix"
    assert matrix["summary"]["status_counts"] == {"ok": 3, "out_of_scope": 1}
    assert matrix["summary"]["below_target_count"] == 1
    assert matrix["summary"]["role_min_scores"]["spec_writer"] == 7.6
    assert matrix["summary"]["out_of_scope_reasons"] == {"unsupported_primary_language_for_python_foundation": 1}
    assert matrix["summary"]["selected_profile_ids"] == {"scheduled_job_acquisition_boundary": 1}
    assert matrix["summary"]["contract_gap_targets"][0]["project"] == "gap"
    assert matrix["summary"]["high_unprofiled_targets"][0]["project"] == "shape_high"


def test_field_trial_matrix_summary_view_omits_rows(tmp_path):
    path = tmp_path / "report.json"
    path.write_text(json.dumps({"cases": [{"project": "a", "status": "ok"}]}), encoding="utf-8")

    summary = summary_view(build_matrix(path))

    assert summary["project_count"] == 1
    assert "summary" in summary
    assert "rows" not in summary
