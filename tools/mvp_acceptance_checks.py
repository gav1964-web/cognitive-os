"""Check predicates for MVP acceptance scenarios."""

from __future__ import annotations

import json
from typing import Any, Callable

Check = Callable[[dict[str, Any]], tuple[bool, str]]

def returncode_ok(ctx: dict[str, Any]) -> tuple[bool, str]: return ctx["returncode"] == 0, "returncode is 0" if ctx["returncode"] == 0 else "non-zero returncode"


def json_status(expected: str) -> Check:
    def check(ctx: dict[str, Any]) -> tuple[bool, str]:
        payload = ctx["payload"]
        actual = payload.get("status") if isinstance(payload, dict) else None
        return ctx["returncode"] == 0 and actual == expected, f"status={actual}, expected={expected}"

    return check


def json_status_ok(ctx: dict[str, Any]) -> tuple[bool, str]: return json_status("ok")(ctx)
def json_status_created(ctx: dict[str, Any]) -> tuple[bool, str]: return json_status("created")(ctx)
def json_status_queued(ctx: dict[str, Any]) -> tuple[bool, str]: return json_status("queued")(ctx)

def happy_path_ok(ctx: dict[str, Any]) -> tuple[bool, str]:
    payload = ctx["payload"]
    ok = (
        ctx["returncode"] == 0
        and payload.get("status") == "ok"
        and payload.get("state") == "STOPPED"
        and payload.get("completed_nodes") == ["fetch", "parse", "save"]
    )
    return ok, f"status={payload.get('status')}, nodes={payload.get('completed_nodes')}"


def quarantine_ok(ctx: dict[str, Any]) -> tuple[bool, str]:
    payload = ctx["payload"]
    parse_output = dict(payload.get("outputs", {})).get("parse", {})
    ok = ctx["returncode"] == 0 and parse_output.get("title") == "recovered by fallback"
    return ok, f"parse.title={parse_output.get('title')}"


def controlled_stop_ok(ctx: dict[str, Any]) -> tuple[bool, str]:
    payload = ctx["payload"]
    ok = ctx["returncode"] == 0 and payload.get("status") in {"ok", "stopped"} and payload.get("state") in {"STOPPED", "FAILED"}
    return ok, f"status={payload.get('status')}, state={payload.get('state')}"


def worker_pool_ok(ctx: dict[str, Any]) -> tuple[bool, str]:
    payload = ctx["payload"]
    if not isinstance(payload, dict):
        return False, "worker pool did not return JSON payload"
    results = payload.get("results", []) if isinstance(payload, dict) else []
    completed = [
        item
        for item in results
        if item.get("status") == "completed"
        and item.get("result_status") == "ok"
        and int(item.get("packet_count", 0)) > 0
    ]
    ok = ctx["returncode"] == 0 and int(payload.get("processed", 0)) >= 1 and bool(completed)
    return ok, f"processed={payload.get('processed')}, completed_ok={len(completed)}"


def queue_has_completed(job_id: str | None) -> Check:
    def check(ctx: dict[str, Any]) -> tuple[bool, str]:
        payload = ctx["payload"]
        jobs = payload.get("jobs", []) if isinstance(payload, dict) else []
        matching = [job for job in jobs if job.get("job_id") == job_id]
        packet_count = int(matching[0].get("packet_count", 0)) if matching else 0
        ok = (
            ctx["returncode"] == 0
            and bool(matching)
            and matching[0].get("status") in {"completed", "succeeded"}
            and packet_count > 0
        )
        status = matching[0].get("status") if matching else None
        return ok, f"job_id={job_id}, status={status}, packets={packet_count}"

    return check


def memory_template_mature(ctx: dict[str, Any]) -> tuple[bool, str]:
    payload = ctx["payload"]
    templates = payload.get("templates", []) if isinstance(payload, dict) else []
    mature = [item for item in templates if item.get("safety_status") == "mature"]
    return ctx["returncode"] == 0 and bool(mature), f"mature_templates={len(mature)}"


def planner_is_memory_template(ctx: dict[str, Any]) -> tuple[bool, str]:
    ok = ctx["returncode"] == 0 and ctx["payload"].get("planner") == "memory_template"
    return ok, f"planner={ctx['payload'].get('planner')}"


def goal_run_ok(ctx: dict[str, Any]) -> tuple[bool, str]:
    payload = ctx["payload"]
    execution = dict(payload.get("execution", {}))
    plan = dict(payload.get("level35_plan", {}))
    deliberation = dict(payload.get("level4_deliberation", {}))
    selected = dict(deliberation.get("selected_alternative") or {})
    ok = (
        ctx["returncode"] == 0
        and execution.get("status") == "ok"
        and plan.get("planner") == "memory_template"
        and deliberation.get("recommendation") == "continue_to_level35"
        and selected.get("id") in {"memory_template", "deterministic_required_capabilities"}
    )
    return ok, (
        f"execution={execution.get('status')}, planner={plan.get('planner')}, "
        f"l4={deliberation.get('recommendation')}, alternative={selected.get('id')}"
    )


def goal_run_planner_in(expected_planners: set[str]) -> Check:
    def check(ctx: dict[str, Any]) -> tuple[bool, str]:
        payload = ctx["payload"]
        execution = dict(payload.get("execution", {}))
        plan = dict(payload.get("level35_plan", {}))
        deliberation = dict(payload.get("level4_deliberation", {}))
        selected = dict(deliberation.get("selected_alternative") or {})
        planner = plan.get("planner")
        ok = (
            ctx["returncode"] == 0
            and execution.get("status") == "ok"
            and planner in expected_planners
            and deliberation.get("recommendation") == "continue_to_level35"
            and selected.get("id") in {"memory_template", "deterministic_required_capabilities", "llm_planner_fallback"}
        )
        return ok, (
            f"execution={execution.get('status')}, planner={planner}, "
            f"l4={deliberation.get('recommendation')}, alternative={selected.get('id')}"
        )

    return check


def spinal_benchmark_ok(ctx: dict[str, Any]) -> tuple[bool, str]:
    payload = ctx["payload"]
    summary = dict(payload.get("summary", {})) if isinstance(payload, dict) else {}
    ok = (
        ctx["returncode"] == 0
        and payload.get("status") == "ok"
        and int(summary.get("case_count", 0)) >= 8
        and float(summary.get("route_accuracy", 0.0)) == 1.0
        and float(summary.get("packet_contract_rate", 0.0)) == 1.0
        and float(summary.get("recovery_accuracy", 0.0)) == 1.0
    )
    return ok, (
        f"cases={summary.get('case_count')}, routes={summary.get('route_accuracy')}, "
        f"packets={summary.get('packet_contract_rate')}, recovery={summary.get('recovery_accuracy')}"
    )


def project_analyzer_benchmark_ok(ctx: dict[str, Any]) -> tuple[bool, str]:
    payload = ctx["payload"]
    summary = dict(payload.get("summary", {})) if isinstance(payload, dict) else {}
    recall = float(summary.get("recall", 0.0) or 0.0)
    ok = ctx["returncode"] == 0 and payload.get("status") == "ok" and int(payload.get("project_count", 0)) >= 8 and recall >= 0.85
    return ok, f"projects={payload.get('project_count')}, recall={recall}"


def l4_quality_probe_ok(ctx: dict[str, Any]) -> tuple[bool, str]:
    payload = ctx["payload"]; summary = dict(payload.get("summary", {})) if isinstance(payload, dict) else {}
    count = int(payload.get("project_count", 0) or 0); quality = float(summary.get("avg_quality_score", 0.0) or 0.0)
    ok = ctx["returncode"] == 0 and payload.get("status") == "ok" and count >= 10 and quality >= 0.9 and int(summary.get("quality_passed", 0) or 0) == count and int(summary.get("quality_warnings", 0) or 0) == 0 and int(summary.get("l4_invoked", 0) or 0) == count and int(summary.get("fallbacks", 0) or 0) == 0
    return ok, f"projects={count}, quality={quality}, warnings={summary.get('quality_warnings')}"


def extraction_proposal_ok(ctx: dict[str, Any]) -> tuple[bool, str]:
    payload = ctx["payload"]
    spec = dict(payload.get("proposed_spec", {})) if isinstance(payload, dict) else {}
    safety = dict(payload.get("safety", {})) if isinstance(payload, dict) else {}
    ok = (
        ctx["returncode"] == 0
        and payload.get("status") == "ok"
        and bool(payload.get("proposal_path"))
        and bool(payload.get("spec_path"))
        and safety.get("source_code_changes") is False
        and bool(spec.get("source_extraction"))
    )
    return ok, f"status={payload.get('status')}, spec={spec.get('id')}"


def project_transform_ok(ctx: dict[str, Any]) -> tuple[bool, str]:
    payload = ctx["payload"]
    safety = dict(payload.get("safety", {})) if isinstance(payload, dict) else {}
    dry_run = dict(payload.get("dry_run_promotion", {})) if isinstance(payload, dict) else {}
    ok = (
        ctx["returncode"] == 0
        and payload.get("status") == "promotion_ready"
        and dry_run.get("status") == "dry_run_passed"
        and bool(payload.get("candidate_path"))
        and bool(payload.get("report_path"))
        and safety.get("source_code_changes") is False
        and safety.get("registry_changes") is False
    )
    return ok, f"status={payload.get('status')}, dry_run={dry_run.get('status')}"


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


def dialogue_recall_ok(ctx: dict[str, Any]) -> tuple[bool, str]:
    payload = ctx["payload"]
    matches = payload.get("matches", []) if isinstance(payload, dict) else []
    kind = matches[0].get("kind") if matches else None
    ok = ctx["returncode"] == 0 and bool(matches) and kind in {"principle", "turn", "topic"}
    return ok, f"matches={len(matches)}, first_kind={kind}"


def dialogue_compact_ok(ctx: dict[str, Any]) -> tuple[bool, str]:
    kind = dict(ctx["payload"].get("summary", {})).get("kind") if isinstance(ctx["payload"], dict) else None
    ok = ctx["returncode"] == 0 and ctx["payload"].get("status") == "ok" and kind == "summary"
    return ok, f"summary_kind={kind}"


def dialogue_topic_graph_ok(ctx: dict[str, Any]) -> tuple[bool, str]:
    nodes = ctx["payload"].get("nodes", []) if isinstance(ctx["payload"], dict) else []
    return ctx["returncode"] == 0 and ctx["payload"].get("status") == "ok" and bool(nodes), f"nodes={len(nodes)}"


def json_or_empty(text: str) -> dict[str, Any] | None:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def payload_summary(payload: dict[str, Any]) -> dict[str, Any]:
    keys = ["status", "state", "job_id", "planner", "template_id", "report_path", "report_json", "report_markdown"]
    return {key: payload[key] for key in keys if key in payload}
