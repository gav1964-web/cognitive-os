from __future__ import annotations

from typing import Any

from runtime._parts.config_doctor_common import _Check


def check_project_development_feedback(policy: dict[str, Any], check: _Check) -> None:
    feedback = dict(policy.get("feedback_policy") or {})
    for field_name in (
        "automatic_retry", "preserve_allowed_targets", "research_reasons",
        "research_reason_suffixes", "controlled_stop_reasons", "decisions",
        "minimum_replan_confidence", "allowed_hypothesis_kinds", "architect_decisions",
        "knowledge_catalogs",
    ):
        if field_name not in feedback or feedback.get(field_name) in (None, "", []):
            check.errors.append(f"project_development_policy_missing:feedback_policy.{field_name}")
    if feedback.get("automatic_retry") is not False:
        check.errors.append("project_development_policy_invalid:feedback_policy.automatic_retry")
    if feedback.get("preserve_allowed_targets") is not True:
        check.errors.append("project_development_policy_invalid:feedback_policy.preserve_allowed_targets")
    if set(feedback.get("decisions") or []) != {
        "research", "needs_replanning", "controlled_stop", "completed",
    }:
        check.errors.append("project_development_policy_invalid:feedback_policy.decisions")
    if not 0.0 < float(feedback.get("minimum_replan_confidence") or 0.0) <= 1.0:
        check.errors.append("project_development_policy_invalid:feedback_policy.minimum_replan_confidence")
    if set(feedback.get("architect_decisions") or []) != {
        "replan", "research_more", "controlled_stop",
    }:
        check.errors.append("project_development_policy_invalid:feedback_policy.architect_decisions")
    if set(feedback.get("allowed_hypothesis_kinds") or []) != {
        "exception_pickle_reconstruction_boundary",
        "nested_loop_mapping_boundary",
        "cross_reducer_ambiguity",
        "unsupported_reducer_shape",
    }:
        check.errors.append("project_development_policy_invalid:feedback_policy.allowed_hypothesis_kinds")
    if dict(feedback.get("knowledge_catalogs") or {}) != {
        "boundary_profiles": "knowledge/role_knowledge/project_development_boundary_profiles.json",
        "source_contrasts": "knowledge/role_knowledge/project_development_source_contrasts.json",
    }:
        check.errors.append("project_development_policy_invalid:feedback_policy.knowledge_catalogs")
    _check_replan_revision(feedback, check)


def _check_replan_revision(feedback: dict[str, Any], check: _Check) -> None:
    revision = dict(feedback.get("replan_revision") or {})
    for field_name in (
        "planning_only", "maximum_revision_increment", "preserve_allowed_targets",
        "preserve_required_checks", "developer_handoff_allowed", "executor_rerun_allowed",
        "source_changes_allowed", "statuses",
    ):
        if field_name not in revision or revision.get(field_name) in (None, "", []):
            check.errors.append(
                f"project_development_policy_missing:feedback_policy.replan_revision.{field_name}"
            )
    for field_name in ("planning_only", "preserve_allowed_targets", "preserve_required_checks"):
        if revision.get(field_name) is not True:
            check.errors.append(
                f"project_development_policy_invalid:feedback_policy.replan_revision.{field_name}"
            )
    for field_name in (
        "developer_handoff_allowed", "executor_rerun_allowed", "source_changes_allowed",
    ):
        if revision.get(field_name) is not False:
            check.errors.append(
                f"project_development_policy_invalid:feedback_policy.replan_revision.{field_name}"
            )
    if revision.get("maximum_revision_increment") != 1:
        check.errors.append(
            "project_development_policy_invalid:feedback_policy.replan_revision.maximum_revision_increment"
        )
    if set(revision.get("statuses") or []) != {"planning_only", "blocked"}:
        check.errors.append(
            "project_development_policy_invalid:feedback_policy.replan_revision.statuses"
        )
    _check_bounded_experiment(revision, check)


def _check_bounded_experiment(revision: dict[str, Any], check: _Check) -> None:
    bounded = dict(revision.get("bounded_experiment") or {})
    for field_name in (
        "enabled", "maximum_targets", "maximum_source_files", "maximum_contrast_sources",
        "maximum_evidence_requirements", "maximum_observations", "execution_authorized",
        "read_only_research_enabled", "network_allowed", "subprocess_allowed",
        "allowed_actions", "required_stop_conditions", "proposal_statuses",
        "admission_statuses", "evidence_statuses", "architect_evidence_decisions",
    ):
        if field_name not in bounded or bounded.get(field_name) in (None, "", []):
            check.errors.append(
                "project_development_policy_missing:"
                f"feedback_policy.replan_revision.bounded_experiment.{field_name}"
            )
    if bounded.get("enabled") is not True:
        check.errors.append(
            "project_development_policy_invalid:"
            "feedback_policy.replan_revision.bounded_experiment.enabled"
        )
    if bounded.get("execution_authorized") is not False:
        check.errors.append(
            "project_development_policy_invalid:"
            "feedback_policy.replan_revision.bounded_experiment.execution_authorized"
        )
    if bounded.get("read_only_research_enabled") is not True:
        check.errors.append(
            "project_development_policy_invalid:feedback_policy.replan_revision."
            "bounded_experiment.read_only_research_enabled"
        )
    for field_name in ("network_allowed", "subprocess_allowed"):
        if bounded.get(field_name) is not False:
            check.errors.append(
                "project_development_policy_invalid:feedback_policy.replan_revision."
                f"bounded_experiment.{field_name}"
            )
    expected_values = {
        "maximum_targets": 1,
        "maximum_source_files": 2,
        "maximum_contrast_sources": 1,
        "maximum_evidence_requirements": 3,
        "maximum_observations": 3,
    }
    for field_name, expected in expected_values.items():
        if bounded.get(field_name) != expected:
            check.errors.append(
                "project_development_policy_invalid:feedback_policy.replan_revision."
                f"bounded_experiment.{field_name}"
            )
    _check_bounded_sets(bounded, check)
    _check_human_approval(bounded, check)


def _check_bounded_sets(bounded: dict[str, Any], check: _Check) -> None:
    if set(bounded.get("allowed_actions") or []) != {
        "inspect_source", "read_allowlisted_contrast", "compare_source_shapes",
        "revise_planning_artifacts",
    }:
        check.errors.append(
            "project_development_policy_invalid:"
            "feedback_policy.replan_revision.bounded_experiment.allowed_actions"
        )
    if set(bounded.get("required_stop_conditions") or []) != {
        "target_drift", "evidence_missing", "budget_exhausted", "implementation_required",
    }:
        check.errors.append(
            "project_development_policy_invalid:"
            "feedback_policy.replan_revision.bounded_experiment.required_stop_conditions"
        )
    if set(bounded.get("proposal_statuses") or []) != {"proposed", "blocked"}:
        check.errors.append(
            "project_development_policy_invalid:"
            "feedback_policy.replan_revision.bounded_experiment.proposal_statuses"
        )
    if set(bounded.get("admission_statuses") or []) != {"admitted_for_planning", "blocked"}:
        check.errors.append(
            "project_development_policy_invalid:"
            "feedback_policy.replan_revision.bounded_experiment.admission_statuses"
        )
    if set(bounded.get("evidence_statuses") or []) != {"collected", "incomplete", "blocked"}:
        check.errors.append(
            "project_development_policy_invalid:feedback_policy.replan_revision."
            "bounded_experiment.evidence_statuses"
        )
    if set(bounded.get("architect_evidence_decisions") or []) != {
        "evidence_accepted", "research_more", "controlled_stop",
    }:
        check.errors.append(
            "project_development_policy_invalid:feedback_policy.replan_revision."
            "bounded_experiment.architect_evidence_decisions"
        )


def _check_human_approval(bounded: dict[str, Any], check: _Check) -> None:
    approval = dict(bounded.get("human_approval") or {})
    for field_name in (
        "required", "allowed_decisions", "allowed_authorities", "request_statuses",
        "validation_statuses", "candidate_statuses", "maximum_candidate_targets",
        "execution_authorized", "developer_handoff_allowed", "executor_rerun_allowed",
        "source_changes_allowed", "memory_promotion_allowed",
    ):
        if field_name not in approval or approval.get(field_name) in (None, "", []):
            check.errors.append(
                "project_development_policy_missing:feedback_policy.replan_revision."
                f"bounded_experiment.human_approval.{field_name}"
            )
    if approval.get("required") is not True:
        check.errors.append(
            "project_development_policy_invalid:feedback_policy.replan_revision."
            "bounded_experiment.human_approval.required"
        )
    if set(approval.get("allowed_decisions") or []) != {"approve", "reject"}:
        check.errors.append(
            "project_development_policy_invalid:feedback_policy.replan_revision."
            "bounded_experiment.human_approval.allowed_decisions"
        )
    if set(approval.get("allowed_authorities") or []) != {"human"}:
        check.errors.append(
            "project_development_policy_invalid:feedback_policy.replan_revision."
            "bounded_experiment.human_approval.allowed_authorities"
        )
    if set(approval.get("request_statuses") or []) != {"awaiting_human_approval"}:
        check.errors.append(
            "project_development_policy_invalid:feedback_policy.replan_revision."
            "bounded_experiment.human_approval.request_statuses"
        )
    if set(approval.get("validation_statuses") or []) != {
        "pending", "approved", "rejected", "blocked",
    }:
        check.errors.append(
            "project_development_policy_invalid:feedback_policy.replan_revision."
            "bounded_experiment.human_approval.validation_statuses"
        )
    if set(approval.get("candidate_statuses") or []) != {"approved_not_executable"}:
        check.errors.append(
            "project_development_policy_invalid:feedback_policy.replan_revision."
            "bounded_experiment.human_approval.candidate_statuses"
        )
    if approval.get("maximum_candidate_targets") != 1:
        check.errors.append(
            "project_development_policy_invalid:feedback_policy.replan_revision."
            "bounded_experiment.human_approval.maximum_candidate_targets"
        )
    for field_name in (
        "execution_authorized", "developer_handoff_allowed", "executor_rerun_allowed",
        "source_changes_allowed", "memory_promotion_allowed",
    ):
        if approval.get(field_name) is not False:
            check.errors.append(
                "project_development_policy_invalid:feedback_policy.replan_revision."
                f"bounded_experiment.human_approval.{field_name}"
            )
    _check_implementation_design(approval, check)


def _check_implementation_design(approval: dict[str, Any], check: _Check) -> None:
    design = dict(approval.get("implementation_design") or {})
    for field_name in (
        "enabled", "allowed_candidate_statuses", "maximum_targets", "required_outputs",
        "forbidden_outputs", "automatic_role_invocation", "execution_authorized",
        "developer_handoff_allowed", "executor_rerun_allowed", "source_changes_allowed",
        "memory_promotion_allowed", "allowed_authorities", "design_statuses",
        "validation_statuses", "next_gate", "statuses",
    ):
        if field_name not in design or design.get(field_name) in (None, "", []):
            check.errors.append(
                "project_development_policy_missing:feedback_policy.replan_revision."
                f"bounded_experiment.human_approval.implementation_design.{field_name}"
            )
    expected_design = {
        "enabled": True,
        "allowed_candidate_statuses": {"approved_not_executable"},
        "maximum_targets": 1,
        "allowed_authorities": {"architect"},
        "design_statuses": {"designed_not_executable"},
        "validation_statuses": {"accepted_not_executable", "blocked"},
        "next_gate": "separate_implementation_authorization",
        "statuses": {"ready_for_architect_design", "blocked"},
    }
    _check_implementation_design_expected(design, expected_design, check)
    for field_name in (
        "automatic_role_invocation", "execution_authorized", "developer_handoff_allowed",
        "executor_rerun_allowed", "source_changes_allowed", "memory_promotion_allowed",
    ):
        if design.get(field_name) is not False:
            check.errors.append(
                "project_development_policy_invalid:feedback_policy.replan_revision."
                f"bounded_experiment.human_approval.implementation_design.{field_name}"
            )
    _check_implementation_authorization(design, check)


def _check_implementation_design_expected(
    design: dict[str, Any],
    expected_design: dict[str, Any],
    check: _Check,
) -> None:
    if design.get("enabled") is not expected_design["enabled"]:
        check.errors.append(
            "project_development_policy_invalid:feedback_policy.replan_revision."
            "bounded_experiment.human_approval.implementation_design.enabled"
        )
    for field_name in (
        "allowed_candidate_statuses", "allowed_authorities", "design_statuses",
        "validation_statuses", "statuses",
    ):
        if set(design.get(field_name) or []) != expected_design[field_name]:
            check.errors.append(
                "project_development_policy_invalid:feedback_policy.replan_revision."
                f"bounded_experiment.human_approval.implementation_design.{field_name}"
            )
    if design.get("maximum_targets") != expected_design["maximum_targets"]:
        check.errors.append(
            "project_development_policy_invalid:feedback_policy.replan_revision."
            "bounded_experiment.human_approval.implementation_design.maximum_targets"
        )
    if design.get("required_outputs") != [
        "interface_boundary", "transformation_steps", "acceptance_mapping", "rollback_strategy",
    ]:
        check.errors.append(
            "project_development_policy_invalid:feedback_policy.replan_revision."
            "bounded_experiment.human_approval.implementation_design.required_outputs"
        )
    if set(design.get("forbidden_outputs") or []) != {
        "source_patch", "implementation_plan", "executor_task",
    }:
        check.errors.append(
            "project_development_policy_invalid:feedback_policy.replan_revision."
            "bounded_experiment.human_approval.implementation_design.forbidden_outputs"
        )
    if design.get("next_gate") != expected_design["next_gate"]:
        check.errors.append(
            "project_development_policy_invalid:feedback_policy.replan_revision."
            "bounded_experiment.human_approval.implementation_design.next_gate"
        )


def _check_implementation_authorization(design: dict[str, Any], check: _Check) -> None:
    authorization = dict(design.get("implementation_authorization") or {})
    required_authorization = {
        "enabled", "allowed_decisions", "allowed_authorities", "maximum_targets",
        "operator_id", "required_hypothesis_kind", "required_constructor_inputs",
        "reconstruction_method", "sandbox_implementation_allowed",
        "targeted_verification_required", "regression_verification_required",
        "generated_function_stubs_allowed", "source_apply_allowed",
        "memory_promotion_allowed", "request_statuses", "validation_statuses",
    }
    for field_name in sorted(required_authorization):
        if field_name not in authorization or authorization.get(field_name) in (None, "", []):
            check.errors.append(
                "project_development_policy_missing:feedback_policy.replan_revision."
                "bounded_experiment.human_approval.implementation_design."
                f"implementation_authorization.{field_name}"
            )
    expected_authorization = {
        "enabled": True,
        "allowed_decisions": ["approve", "reject"],
        "allowed_authorities": ["human"],
        "maximum_targets": 1,
        "operator_id": "preserve_exception_constructor_reconstruction",
        "required_hypothesis_kind": "exception_pickle_reconstruction_boundary",
        "required_constructor_inputs": ["allowed", "host"],
        "reconstruction_method": "__reduce__",
        "sandbox_implementation_allowed": True,
        "targeted_verification_required": True,
        "regression_verification_required": True,
        "generated_function_stubs_allowed": False,
        "source_apply_allowed": False,
        "memory_promotion_allowed": False,
        "request_statuses": ["awaiting_human_approval"],
        "validation_statuses": ["pending", "approved", "rejected", "blocked"],
    }
    for field_name, expected in expected_authorization.items():
        if authorization.get(field_name) != expected:
            check.errors.append(
                "project_development_policy_invalid:feedback_policy.replan_revision."
                "bounded_experiment.human_approval.implementation_design."
                f"implementation_authorization.{field_name}"
            )
