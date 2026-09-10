"""Role and curriculum predicates for MVP acceptance."""

from __future__ import annotations

from typing import Any

def architect_role_skill_ok(ctx: dict[str, Any]) -> tuple[bool, str]:
    payload = ctx["payload"]
    next_artifact = dict(payload.get("next_artifact", {})) if isinstance(payload, dict) else {}
    ok = (
        ctx["returncode"] == 0
        and payload.get("artifact_type") == "ArchitectureDecisionRecord"
        and payload.get("role") == "architect"
        and payload.get("status") == "ok"
        and bool(payload.get("subsystem_boundaries"))
        and bool(payload.get("capability_model"))
        and bool(payload.get("architecture_options"))
        and bool(payload.get("chosen_option"))
        and bool(payload.get("rejected_options"))
        and bool(payload.get("spec_writer_brief"))
        and next_artifact.get("recommended_role") == "spec_writer"
        and payload.get("forbidden_actions_observed") == []
        and bool(payload.get("artifact_path"))
    )
    return ok, f"artifact={payload.get('artifact_type')}, next={next_artifact.get('recommended_role')}"

def spec_writer_role_skill_ok(ctx: dict[str, Any]) -> tuple[bool, str]:
    payload = ctx["payload"]
    handoff = dict(payload.get("implementation_handoff", {})) if isinstance(payload, dict) else {}
    ok = (
        ctx["returncode"] == 0
        and payload.get("artifact_type") == "TechnicalSpec"
        and payload.get("role") == "spec_writer"
        and payload.get("status") == "ok"
        and bool(payload.get("requirements"))
        and bool(payload.get("acceptance_criteria"))
        and bool(payload.get("traceability_table"))
        and handoff.get("recommended_role") == "implementer"
        and payload.get("forbidden_actions_observed") == []
        and bool(payload.get("artifact_path"))
    )
    return ok, f"artifact={payload.get('artifact_type')}, handoff={handoff.get('recommended_role')}"

def implementer_role_skill_ok(ctx: dict[str, Any]) -> tuple[bool, str]:
    payload = ctx["payload"]
    next_artifact = dict(payload.get("next_artifact", {})) if isinstance(payload, dict) else {}
    ok = (
        ctx["returncode"] == 0
        and payload.get("artifact_type") == "ImplementationPlan"
        and payload.get("role") == "implementer"
        and payload.get("status") == "ok"
        and bool(payload.get("patch_scope"))
        and bool(payload.get("expected_files"))
        and bool(payload.get("verification_commands"))
        and bool(payload.get("rollback_plan"))
        and bool(payload.get("acceptance_mapping"))
        and next_artifact.get("recommended_role") == "tester"
        and payload.get("forbidden_actions_observed") == []
        and bool(payload.get("artifact_path"))
    )
    return ok, f"artifact={payload.get('artifact_type')}, next={next_artifact.get('recommended_role')}"

def tester_role_skill_ok(ctx: dict[str, Any]) -> tuple[bool, str]:
    payload = ctx["payload"]
    next_artifact = dict(payload.get("next_artifact", {})) if isinstance(payload, dict) else {}
    ok = (
        ctx["returncode"] == 0
        and payload.get("artifact_type") == "TestPlan"
        and payload.get("role") == "tester"
        and payload.get("status") == "ok"
        and bool(payload.get("acceptance_tests"))
        and bool(payload.get("negative_tests"))
        and bool(payload.get("smoke_checklist"))
        and bool(payload.get("regression_risks"))
        and bool(payload.get("reproducibility"))
        and next_artifact.get("recommended_role") == "reviewer"
        and payload.get("forbidden_actions_observed") == []
        and bool(payload.get("artifact_path"))
    )
    return ok, f"artifact={payload.get('artifact_type')}, next={next_artifact.get('recommended_role')}"

def reviewer_role_skill_ok(ctx: dict[str, Any]) -> tuple[bool, str]:
    payload = ctx["payload"]
    ok = (
        ctx["returncode"] == 0
        and payload.get("artifact_type") == "ReviewFindings"
        and payload.get("role") == "reviewer"
        and payload.get("status") == "ok"
        and bool(payload.get("findings"))
        and bool(payload.get("risk_assessment"))
        and isinstance(payload.get("contract_violations"), list)
        and isinstance(payload.get("architecture_drift"), list)
        and payload.get("recommendation") in {"approve", "approve_with_risks", "request_rework"}
        and payload.get("forbidden_actions_observed") == []
        and bool(payload.get("artifact_path"))
    )
    return ok, f"artifact={payload.get('artifact_type')}, recommendation={payload.get('recommendation')}"

def role_pipeline_ok(ctx: dict[str, Any]) -> tuple[bool, str]:
    payload = ctx["payload"]
    safety = dict(payload.get("safety", {})) if isinstance(payload, dict) else {}
    artifacts = dict(payload.get("artifacts", {})) if isinstance(payload, dict) else {}
    human_documents = dict(payload.get("human_documents", {})) if isinstance(payload, dict) else {}
    ok = (
        ctx["returncode"] == 0
        and payload.get("status") == "ok"
        and payload.get("kind") == "role_pipeline"
        and payload.get("next_action") in {"run_project_transform", "review_risks_then_run_project_transform", "rework_role_artifacts"}
        and safety.get("source_code_changes") is False
        and safety.get("registry_changes") is False
        and safety.get("foundry_invoked") is False
        and safety.get("llm_invoked") is False
        and bool(payload.get("report_path"))
        and bool(human_documents.get("architecture_analysis"))
        and dict(artifacts.get("review_findings", {})).get("artifact_type") == "ReviewFindings"
    )
    return ok, f"next_action={payload.get('next_action')}, recommendation={payload.get('recommendation')}"

def role_foundation_ok(ctx: dict[str, Any]) -> tuple[bool, str]:
    payload = ctx["payload"]
    summary = dict(payload.get("summary", {})) if isinstance(payload, dict) else {}
    human_documents = dict(payload.get("human_documents", {})) if isinstance(payload, dict) else {}
    case_docs = [dict(case.get("human_documents", {})).get("architecture_analysis") for case in payload.get("cases", []) if isinstance(case, dict)]
    artifact_score = float(summary.get("artifact_score", 0.0) or 0.0)
    candidate_match_score = float(summary.get("candidate_match_score", 0.0) or 0.0)
    ok = (
        ctx["returncode"] == 0
        and payload.get("status") == "ok"
        and payload.get("milestone") == "Role Foundation Field Trial v0.1"
        and int(payload.get("project_count", 0)) == 1
        and artifact_score == 1.0
        and candidate_match_score == 1.0
        and summary.get("llm_invoked") == 0
        and bool(payload.get("report_path"))
        and (bool(human_documents.get("architecture_analysis")) or any(case_docs))
    )
    return ok, f"projects={payload.get('project_count')}, artifact={artifact_score}, candidate={candidate_match_score}"

def role_pipeline_benchmark_ok(ctx: dict[str, Any]) -> tuple[bool, str]:
    payload = ctx["payload"]
    summary = dict(payload.get("summary", {})) if isinstance(payload, dict) else {}
    artifact_score = float(summary.get("artifact_score", 0.0) or 0.0)
    safety_score = float(summary.get("safety_score", 0.0) or 0.0)
    implementation_score = float(summary.get("implementation_score", 0.0) or 0.0)
    qa_score = float(summary.get("qa_score", 0.0) or 0.0)
    ok = (
        ctx["returncode"] == 0
        and payload.get("status") == "ok"
        and int(payload.get("project_count", 0)) >= 8
        and artifact_score >= 0.95
        and implementation_score == 1.0
        and qa_score == 1.0
        and safety_score == 1.0
        and bool(payload.get("report_path"))
    )
    return ok, (
        f"projects={payload.get('project_count')}, artifact={artifact_score}, "
        f"implementation={implementation_score}, qa={qa_score}, safety={safety_score}"
    )

def spec_writer_curriculum_ok(ctx: dict[str, Any]) -> tuple[bool, str]:
    payload = ctx["payload"]
    summary = dict(payload.get("summary", {})) if isinstance(payload, dict) else {}
    invariants = dict(payload.get("invariants", {})) if isinstance(payload, dict) else {}
    score = float(summary.get("score", 0.0) or 0.0)
    ok = (
        ctx["returncode"] == 0
        and payload.get("status") == "ok"
        and int(payload.get("project_count", 0)) == 3
        and score == 1.0
        and int(summary.get("backlog_items", 0)) == 0
        and invariants.get("teacher_reference_is_ground_truth") is False
        and invariants.get("improvement_protocol") == "external_teacher_corrector_loop"
        and invariants.get("automatic_code_changes_from_own_output") is False
    )
    return ok, f"projects={payload.get('project_count')}, score={score}, backlog={summary.get('backlog_items')}"

def implementer_curriculum_ok(ctx: dict[str, Any]) -> tuple[bool, str]:
    payload = ctx["payload"]
    summary = dict(payload.get("summary", {})) if isinstance(payload, dict) else {}
    invariants = dict(payload.get("invariants", {})) if isinstance(payload, dict) else {}
    score = float(summary.get("score", 0.0) or 0.0)
    ok = (
        ctx["returncode"] == 0
        and payload.get("status") == "ok"
        and int(payload.get("project_count", 0)) == 3
        and score == 1.0
        and int(summary.get("backlog_items", 0)) == 0
        and invariants.get("teacher_reference_is_ground_truth") is False
        and invariants.get("improvement_protocol") == "external_teacher_corrector_loop"
        and invariants.get("automatic_code_changes_from_own_output") is False
        and invariants.get("source_code_changes") is False
        and invariants.get("registry_changes") is False
        and invariants.get("foundry_or_promote_not_in_scope") is True
    )
    return ok, f"projects={payload.get('project_count')}, score={score}, backlog={summary.get('backlog_items')}"

def tester_curriculum_ok(ctx: dict[str, Any]) -> tuple[bool, str]:
    payload = ctx["payload"]
    summary = dict(payload.get("summary", {})) if isinstance(payload, dict) else {}
    invariants = dict(payload.get("invariants", {})) if isinstance(payload, dict) else {}
    worst = float(summary.get("worst_case_score", 0.0) or 0.0)
    ok = (
        ctx["returncode"] == 0
        and payload.get("status") == "ok"
        and int(payload.get("project_count", 0)) == 3
        and worst >= float(summary.get("ready_threshold", 0.92) or 0.92)
        and summary.get("ready_by_worst_case") is True
        and int(summary.get("backlog_items", 0)) == 0
        and invariants.get("teacher_reference_is_ground_truth") is False
        and invariants.get("improvement_protocol") == "external_teacher_corrector_loop"
        and invariants.get("automatic_code_changes_from_own_output") is False
        and invariants.get("source_code_changes") is False
        and invariants.get("registry_changes") is False
        and invariants.get("foundry_or_promote_not_in_scope") is True
    )
    return ok, f"projects={payload.get('project_count')}, worst={worst}, backlog={summary.get('backlog_items')}"

def reviewer_curriculum_ok(ctx: dict[str, Any]) -> tuple[bool, str]:
    payload = ctx["payload"]
    summary = dict(payload.get("summary", {})) if isinstance(payload, dict) else {}
    invariants = dict(payload.get("invariants", {})) if isinstance(payload, dict) else {}
    worst = float(summary.get("worst_case_score", 0.0) or 0.0)
    ok = (
        ctx["returncode"] == 0
        and payload.get("status") == "ok"
        and int(payload.get("project_count", 0)) == 3
        and worst >= float(summary.get("ready_threshold", 0.92) or 0.92)
        and summary.get("ready_by_worst_case") is True
        and int(summary.get("backlog_items", 0)) == 0
        and invariants.get("teacher_reference_is_ground_truth") is False
        and invariants.get("improvement_protocol") == "external_teacher_corrector_loop"
        and invariants.get("automatic_code_changes_from_own_output") is False
        and invariants.get("source_code_changes") is False
        and invariants.get("registry_changes") is False
        and invariants.get("foundry_or_promote_not_in_scope") is True
    )
    return ok, f"projects={payload.get('project_count')}, worst={worst}, backlog={summary.get('backlog_items')}"
