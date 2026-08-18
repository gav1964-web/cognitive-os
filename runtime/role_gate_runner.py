"""Stable facade for split `role_gate_runner` implementation."""

from __future__ import annotations

import importlib

_PART_NAMES = ['role_gate_runner_part1', 'role_gate_runner_part2']
_PARTS = [importlib.import_module(f"runtime._parts.{part}") for part in _PART_NAMES]
_MERGED = {}
for _part in _PARTS:
    _MERGED.update({key: value for key, value in vars(_part).items() if not key.startswith("__")})
for _part in _PARTS:
    vars(_part).update(_MERGED)
globals().update(_MERGED)

_CHECK_NAMES = [
    "project_path_exists",
    "python_project_scope",
    "bounded_file_scan",
    "answers_source_linked",
    "entrypoints_detected",
    "runtime_extraction_readiness_present",
    "task_inputs_outputs_and_code_areas_present",
    "entrypoints_or_runtime_commands_detected",
    "execution_path_pipeline_candidate_present",
    "capability_candidates_or_controlled_gap_present",
    "contracts_data_and_weak_zones_reported",
    "errors_state_reproducibility_explicit",
    "data_lifecycle_present",
    "runtime_extraction_plan_present",
    "project_report_has_evidence",
    "chosen_option_required",
    "traceability_required",
    "decision_has_source_evidence",
    "risks_are_actionable",
    "handoff_is_typed",
    "options_include_tradeoffs",
    "subsystem_boundaries_have_inputs_outputs",
    "data_lifecycle_and_state_model_present",
    "spec_writer_brief_has_contract_targets",
    "adr_chosen_option_present",
    "ranked_candidate_present",
    "acceptance_criteria_required",
    "requirements_verifiable",
    "interface_contracts_present",
    "error_model_present",
    "acceptance_criteria_source_linked",
    "contract_shapes_specific",
    "side_effect_gates_present",
    "spec_writer_red_team_passed",
    "state_and_replay_policy_present",
    "traceability_table_present",
    "implementation_handoff_typed",
    "implementation_delta_evidence_bound",
    "technical_spec_contract_present",
    "writable_scope_bounded",
    "verification_commands_allowlisted",
    "plan_has_patch_intent",
    "plan_delta_propagated",
    "executor_handoff_present",
    "rollback_policy_present",
    "contract_test_matrix_required",
    "negative_tests_required",
    "external_calls_faked_by_default",
    "negative_tests_present",
    "contract_matrix_targets_candidate",
    "verification_is_project_scoped",
    "target_or_blocked_handoff_present",
    "dependencies_acyclic",
    "acceptance_coverage_explicit",
    "changes_are_dependency_ordered",
    "acceptance_is_fully_mapped",
    "evidence_refs_present",
    "stop_conditions_explicit",
    "scope_preserved",
    "contract_violations_checked",
    "promotion_requires_human_review",
    "recommendation_explicit",
    "risks_have_mitigation",
    "review_target_matches_plan",
    "evidence_refs_required",
    "source_attribution_required",
    "kb_admission_policy_required",
    "candidate_has_evidence",
    "facts_and_judgments_separated",
    "approval_gates_declared",
]
_CHECKS = {name: globals()[f"_{name}"] for name in _CHECK_NAMES}
globals()["_CHECKS"] = _CHECKS
for _part in _PARTS:
    vars(_part)["_CHECKS"] = _CHECKS

__all__ = ['run_role_gate_report']
