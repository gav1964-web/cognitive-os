"""Execute role_directory gates and quality criteria against produced artifacts."""

from __future__ import annotations

from typing import Any

from .role_directory import load_role_directory


def run_role_gate_report(
    *,
    artifacts: dict[str, dict[str, Any]],
    project_report: dict[str, Any] | None = None,
    directory: dict[str, Any] | None = None,
    mode: str = "strict",
) -> dict[str, Any]:
    if mode not in {"advisory", "strict", "release_required"}:
        raise ValueError(f"unknown role gate mode: {mode}")
    payload = directory or load_role_directory()
    roles = dict(payload.get("roles") or {})
    artifact_by_role = _artifact_by_role(artifacts, project_report)
    cases = []
    for role_id, role in sorted(roles.items(), key=lambda item: int(dict(item[1]).get("order") or 0)):
        if role_id not in artifact_by_role and role_id != "researcher":
            continue
        if role_id == "researcher" and role_id not in artifact_by_role:
            cases.append(_skipped_case(role_id, dict(role), "researcher is not part of default artifact pipeline"))
            continue
        cases.append(_run_role_case(role_id, dict(role), artifact_by_role[role_id], artifacts, project_report or {}))
    failed = [case for case in cases if case["status"] == "failed"]
    warnings = [case for case in cases if case["status"] == "warning"]
    status = _report_status(mode=mode, failed=failed, warnings=warnings)
    return {
        "artifact_type": "RoleGateReport",
        "schema_version": payload.get("schema_version"),
        "mode": mode,
        "status": status,
        "summary": {
            "checked": len([case for case in cases if case["status"] != "skipped"]),
            "failed": len(failed),
            "warnings": len(warnings),
            "skipped": len([case for case in cases if case["status"] == "skipped"]),
            "blocking_failed": len(failed) if mode in {"strict", "release_required"} else 0,
        },
        "blocking_policy": _blocking_policy(mode),
        "cases": cases,
    }


def _report_status(*, mode: str, failed: list[dict[str, Any]], warnings: list[dict[str, Any]]) -> str:
    if mode == "advisory":
        return "warning" if failed or warnings else "ok"
    return "failed" if failed else "ok"


def _blocking_policy(mode: str) -> dict[str, Any]:
    return {
        "mode": mode,
        "advisory_does_not_block": mode == "advisory",
        "strict_blocks_on_failed_gate": mode in {"strict", "release_required"},
        "release_requires_clean_role_gates": mode == "release_required",
    }


def _run_role_case(
    role_id: str,
    role: dict[str, Any],
    artifact: dict[str, Any],
    artifacts: dict[str, dict[str, Any]],
    project_report: dict[str, Any],
) -> dict[str, Any]:
    gate_results = [_evaluate_named_check(name, artifact, artifacts, project_report) for name in role.get("gates", [])]
    quality_results = [
        _evaluate_named_check(name, artifact, artifacts, project_report)
        for name in role.get("quality_criteria", [])
    ]
    failed = [row for row in [*gate_results, *quality_results] if row["status"] == "failed"]
    warnings = _fallback_warnings(role)
    return {
        "role_id": role_id,
        "artifact_type": artifact.get("artifact_type"),
        "status": "failed" if failed else ("warning" if warnings else "ok"),
        "gates": gate_results,
        "quality_criteria": quality_results,
        "fallback_policy": role.get("fallback_policy", {}),
        "warnings": warnings,
    }


def _skipped_case(role_id: str, role: dict[str, Any], reason: str) -> dict[str, Any]:
    return {
        "role_id": role_id,
        "status": "skipped",
        "reason": reason,
        "gates": [{"name": name, "status": "skipped", "reason": reason} for name in role.get("gates", [])],
        "quality_criteria": [
            {"name": name, "status": "skipped", "reason": reason} for name in role.get("quality_criteria", [])
        ],
        "fallback_policy": role.get("fallback_policy", {}),
        "warnings": [],
    }


def _artifact_by_role(artifacts: dict[str, dict[str, Any]], project_report: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    rows = {str(artifact.get("role")): artifact for artifact in artifacts.values() if artifact.get("role")}
    if project_report is not None:
        rows.setdefault(
            "project_analyzer",
            {
                "artifact_type": "ProjectMapReport",
                "role": "project_analyzer",
                "status": "ok",
                "content": project_report,
            },
        )
    return rows


def _evaluate_named_check(
    name: str,
    artifact: dict[str, Any],
    artifacts: dict[str, dict[str, Any]],
    project_report: dict[str, Any],
) -> dict[str, Any]:
    ok, reason = _CHECKS.get(name, _unknown_check)(artifact, artifacts, project_report)
    return {"name": name, "status": "passed" if ok else "failed", "reason": reason}


def _fallback_warnings(role: dict[str, Any]) -> list[str]:
    fallback = dict(role.get("fallback_policy") or {})
    llm = dict(role.get("llm_policy") or {})
    warnings = []
    if llm.get("allowed") and not any("l45" in str(value) or "semantic" in str(value) for value in fallback.values()):
        warnings.append("llm_allowed_without_semantic_fallback")
    return warnings


def _project_path_exists(artifact: dict[str, Any], artifacts: dict[str, dict[str, Any]], project_report: dict[str, Any]) -> tuple[bool, str]:
    summary = dict(project_report.get("summary", {}))
    return bool(summary.get("root") or artifact.get("project")), "project root is recorded"


def _python_project_scope(artifact: dict[str, Any], artifacts: dict[str, dict[str, Any]], project_report: dict[str, Any]) -> tuple[bool, str]:
    summary = dict(project_report.get("summary", {}))
    language_counts = dict(summary.get("language_counts", {}))
    languages = [str(item).lower() for item in list(summary.get("languages") or [])]
    read_files = [str(item).lower() for item in list(summary.get("read_files") or [])]
    return bool(
        language_counts.get(".py")
        or "python" in languages
        or any(item.endswith(".py") for item in read_files)
        or project_report.get("files")
    ), "python files or project files are present"


def _bounded_file_scan(artifact: dict[str, Any], artifacts: dict[str, dict[str, Any]], project_report: dict[str, Any]) -> tuple[bool, str]:
    summary = dict(project_report.get("summary", {}))
    return int(summary.get("file_count") or 0) <= 2000, "scan stays within configured benchmark bound"


def _answers_source_linked(artifact: dict[str, Any], artifacts: dict[str, dict[str, Any]], project_report: dict[str, Any]) -> tuple[bool, str]:
    return bool(project_report.get("answers")), "project answers are present"


def _entrypoints_detected(artifact: dict[str, Any], artifacts: dict[str, dict[str, Any]], project_report: dict[str, Any]) -> tuple[bool, str]:
    answers = dict(project_report.get("answers", {}))
    execution = dict(answers.get("2_entrypoints_and_execution_flow", {}) or answers.get("2_execution", {}))
    return bool(execution.get("entrypoints") or execution.get("primary_execution_path")), "entrypoint or execution path evidence exists"


def _runtime_extraction_readiness_present(artifact: dict[str, Any], artifacts: dict[str, dict[str, Any]], project_report: dict[str, Any]) -> tuple[bool, str]:
    answers = dict(project_report.get("answers", {}))
    return bool(answers.get("6_runtime_extraction_readiness")), "runtime extraction readiness answer exists"


def _project_report_has_evidence(artifact: dict[str, Any], artifacts: dict[str, dict[str, Any]], project_report: dict[str, Any]) -> tuple[bool, str]:
    return bool(project_report.get("answers") or artifact.get("source_context")), "source evidence exists"


def _chosen_option_required(artifact: dict[str, Any], artifacts: dict[str, dict[str, Any]], project_report: dict[str, Any]) -> tuple[bool, str]:
    return bool(dict(artifact.get("chosen_option", {})).get("id")), "chosen option id is present"


def _traceability_required(artifact: dict[str, Any], artifacts: dict[str, dict[str, Any]], project_report: dict[str, Any]) -> tuple[bool, str]:
    return bool(artifact.get("traceability")), "traceability rows are present"


def _decision_has_source_evidence(artifact: dict[str, Any], artifacts: dict[str, dict[str, Any]], project_report: dict[str, Any]) -> tuple[bool, str]:
    return bool(artifact.get("capability_model") or artifact.get("source_context")), "ADR contains source-linked decision evidence"


def _risks_are_actionable(artifact: dict[str, Any], artifacts: dict[str, dict[str, Any]], project_report: dict[str, Any]) -> tuple[bool, str]:
    risks = artifact.get("risks") or artifact.get("risk_assessment") or []
    return bool(risks) and all(isinstance(row, dict) and (row.get("mitigation") or row.get("source") or row.get("severity") == "low") for row in risks), "risks have mitigation/source or are low"


def _handoff_is_typed(artifact: dict[str, Any], artifacts: dict[str, dict[str, Any]], project_report: dict[str, Any]) -> tuple[bool, str]:
    return bool(artifact.get("next_artifact") or artifact.get("spec_writer_brief")), "typed handoff fields exist"


def _adr_chosen_option_present(artifact: dict[str, Any], artifacts: dict[str, dict[str, Any]], project_report: dict[str, Any]) -> tuple[bool, str]:
    adr = dict(artifacts.get("architecture_decision", {}))
    return bool(dict(adr.get("chosen_option", {})).get("id")), "ADR chosen option exists"


def _ranked_candidate_present(artifact: dict[str, Any], artifacts: dict[str, dict[str, Any]], project_report: dict[str, Any]) -> tuple[bool, str]:
    contract = dict(artifact.get("extraction_contract", {}))
    return bool(contract.get("candidate") or contract.get("ranked_candidates") or contract.get("status") == "blocked_no_safe_candidate"), "ranked candidate or controlled block exists"


def _acceptance_criteria_required(artifact: dict[str, Any], artifacts: dict[str, dict[str, Any]], project_report: dict[str, Any]) -> tuple[bool, str]:
    return bool(artifact.get("acceptance_criteria")), "acceptance criteria exist"


def _requirements_verifiable(artifact: dict[str, Any], artifacts: dict[str, dict[str, Any]], project_report: dict[str, Any]) -> tuple[bool, str]:
    return bool(artifact.get("requirements") and artifact.get("acceptance_criteria")), "requirements and acceptance criteria exist"


def _traceability_table_present(artifact: dict[str, Any], artifacts: dict[str, dict[str, Any]], project_report: dict[str, Any]) -> tuple[bool, str]:
    return bool(artifact.get("traceability_table")), "traceability table exists"


def _implementation_handoff_typed(artifact: dict[str, Any], artifacts: dict[str, dict[str, Any]], project_report: dict[str, Any]) -> tuple[bool, str]:
    return bool(dict(artifact.get("implementation_handoff", {})).get("recommended_role")), "implementation handoff names next producer"


def _technical_spec_contract_present(artifact: dict[str, Any], artifacts: dict[str, dict[str, Any]], project_report: dict[str, Any]) -> tuple[bool, str]:
    spec = dict(artifacts.get("technical_spec", {}))
    return bool(spec.get("extraction_contract")), "technical spec extraction contract exists"


def _writable_scope_bounded(artifact: dict[str, Any], artifacts: dict[str, dict[str, Any]], project_report: dict[str, Any]) -> tuple[bool, str]:
    target = str(dict(artifact.get("implementation_target", {})).get("candidate") or "")
    writable = [str(item) for item in artifact.get("writable_scope", []) if item]
    blocked = dict(artifact.get("implementation_target", {})).get("status") == "blocked_no_safe_candidate"
    return blocked or bool(target and writable == [target]), "writable scope is exactly the target candidate"


def _verification_commands_allowlisted(artifact: dict[str, Any], artifacts: dict[str, dict[str, Any]], project_report: dict[str, Any]) -> tuple[bool, str]:
    commands = [str(item).lower() for item in artifact.get("verification_commands", [])]
    return bool(commands) and all("python" in item or "pytest" in item for item in commands), "verification commands are Python/pytest scoped"


def _plan_has_patch_intent(artifact: dict[str, Any], artifacts: dict[str, dict[str, Any]], project_report: dict[str, Any]) -> tuple[bool, str]:
    return dict(artifact.get("patch_intent", {})).get("artifact_type") == "PatchIntent", "PatchIntent is present"


def _executor_handoff_present(artifact: dict[str, Any], artifacts: dict[str, dict[str, Any]], project_report: dict[str, Any]) -> tuple[bool, str]:
    return bool(artifact.get("executor_handoff")), "executor handoff is present"


def _rollback_policy_present(artifact: dict[str, Any], artifacts: dict[str, dict[str, Any]], project_report: dict[str, Any]) -> tuple[bool, str]:
    return bool(dict(artifact.get("rollback_plan", {})).get("registry_policy")), "rollback registry policy is present"


def _contract_test_matrix_required(artifact: dict[str, Any], artifacts: dict[str, dict[str, Any]], project_report: dict[str, Any]) -> tuple[bool, str]:
    return bool(artifact.get("contract_test_matrix")), "contract test matrix exists"


def _negative_tests_required(artifact: dict[str, Any], artifacts: dict[str, dict[str, Any]], project_report: dict[str, Any]) -> tuple[bool, str]:
    return bool(artifact.get("negative_tests")), "negative tests exist"


def _external_calls_faked_by_default(artifact: dict[str, Any], artifacts: dict[str, dict[str, Any]], project_report: dict[str, Any]) -> tuple[bool, str]:
    strategy = dict(artifact.get("test_strategy", {}))
    text = str(strategy).lower()
    requires_external = any(marker in text for marker in ("network", "http", "api", "browser", "subprocess", "external"))
    explicit_fake = "fake" in text or bool(artifact.get("dependency_policy"))
    return (not requires_external) or explicit_fake, "external-call policy is explicit or no external boundary is in scope"


def _negative_tests_present(artifact: dict[str, Any], artifacts: dict[str, dict[str, Any]], project_report: dict[str, Any]) -> tuple[bool, str]:
    return _negative_tests_required(artifact, artifacts, project_report)


def _contract_matrix_targets_candidate(artifact: dict[str, Any], artifacts: dict[str, dict[str, Any]], project_report: dict[str, Any]) -> tuple[bool, str]:
    target = str(dict(artifact.get("test_target", {})).get("candidate") or "")
    rows = artifact.get("contract_test_matrix", [])
    return bool(target and any(isinstance(row, dict) and row.get("target") == target for row in rows)), "contract tests target selected candidate"


def _verification_is_project_scoped(artifact: dict[str, Any], artifacts: dict[str, dict[str, Any]], project_report: dict[str, Any]) -> tuple[bool, str]:
    return bool(artifact.get("smoke_checklist")), "project-scoped smoke checklist exists"


def _scope_preserved(artifact: dict[str, Any], artifacts: dict[str, dict[str, Any]], project_report: dict[str, Any]) -> tuple[bool, str]:
    return dict(artifact.get("coverage_assessment", {})).get("scope_preserved") is True, "review confirms scope preservation"


def _contract_violations_checked(artifact: dict[str, Any], artifacts: dict[str, dict[str, Any]], project_report: dict[str, Any]) -> tuple[bool, str]:
    return isinstance(artifact.get("contract_violations"), list), "contract violations list exists"


def _promotion_requires_human_review(artifact: dict[str, Any], artifacts: dict[str, dict[str, Any]], project_report: dict[str, Any]) -> tuple[bool, str]:
    return "human" in str(artifact).lower() or artifact.get("recommendation") in {"approve_with_risks", "request_rework"}, "human review/promotion caution is represented"


def _recommendation_explicit(artifact: dict[str, Any], artifacts: dict[str, dict[str, Any]], project_report: dict[str, Any]) -> tuple[bool, str]:
    return artifact.get("recommendation") in {"approve", "approve_with_risks", "request_rework"}, "review recommendation is explicit"


def _risks_have_mitigation(artifact: dict[str, Any], artifacts: dict[str, dict[str, Any]], project_report: dict[str, Any]) -> tuple[bool, str]:
    return _risks_are_actionable(artifact, artifacts, project_report)


def _review_target_matches_plan(artifact: dict[str, Any], artifacts: dict[str, dict[str, Any]], project_report: dict[str, Any]) -> tuple[bool, str]:
    reviewed = str(dict(artifact.get("review_target", {})).get("candidate") or "")
    planned = str(dict(dict(artifacts.get("implementation_plan", {})).get("implementation_target", {})).get("candidate") or "")
    blocked = dict(artifact.get("review_target", {})).get("binding_status") == "blocked_no_safe_candidate"
    return blocked or bool(reviewed and reviewed == planned), "review target matches implementation target"


def _evidence_refs_required(artifact: dict[str, Any], artifacts: dict[str, dict[str, Any]], project_report: dict[str, Any]) -> tuple[bool, str]:
    return bool(artifact.get("evidence_refs") or artifact.get("source_cases")), "evidence refs exist"


def _source_attribution_required(artifact: dict[str, Any], artifacts: dict[str, dict[str, Any]], project_report: dict[str, Any]) -> tuple[bool, str]:
    return bool(artifact.get("teacher_reference") or artifact.get("source") or artifact.get("source_cases")), "source attribution exists"


def _kb_admission_policy_required(artifact: dict[str, Any], artifacts: dict[str, dict[str, Any]], project_report: dict[str, Any]) -> tuple[bool, str]:
    policy = dict(artifact.get("evidence_policy", {}))
    return policy.get("automatic_self_promotion_forbidden") is True or artifact.get("kb_policy", {}).get("auto_promote") is False, "KB admission forbids automatic promotion"


def _candidate_has_evidence(artifact: dict[str, Any], artifacts: dict[str, dict[str, Any]], project_report: dict[str, Any]) -> tuple[bool, str]:
    return _evidence_refs_required(artifact, artifacts, project_report)


def _facts_and_judgments_separated(artifact: dict[str, Any], artifacts: dict[str, dict[str, Any]], project_report: dict[str, Any]) -> tuple[bool, str]:
    policy = dict(artifact.get("evidence_policy", {}))
    return policy.get("facts_require_evidence") is True or policy.get("judgments_are_reviewed_separately") is True, "facts and judgments policy exists"


def _approval_gates_declared(artifact: dict[str, Any], artifacts: dict[str, dict[str, Any]], project_report: dict[str, Any]) -> tuple[bool, str]:
    policy = dict(artifact.get("evidence_policy", {}))
    return bool(policy.get("required_approvals")), "required approvals are declared"


def _unknown_check(artifact: dict[str, Any], artifacts: dict[str, dict[str, Any]], project_report: dict[str, Any]) -> tuple[bool, str]:
    return False, "unknown role gate or quality criterion"


_CHECKS = {
    "project_path_exists": _project_path_exists,
    "python_project_scope": _python_project_scope,
    "bounded_file_scan": _bounded_file_scan,
    "answers_source_linked": _answers_source_linked,
    "entrypoints_detected": _entrypoints_detected,
    "runtime_extraction_readiness_present": _runtime_extraction_readiness_present,
    "project_report_has_evidence": _project_report_has_evidence,
    "chosen_option_required": _chosen_option_required,
    "traceability_required": _traceability_required,
    "decision_has_source_evidence": _decision_has_source_evidence,
    "risks_are_actionable": _risks_are_actionable,
    "handoff_is_typed": _handoff_is_typed,
    "adr_chosen_option_present": _adr_chosen_option_present,
    "ranked_candidate_present": _ranked_candidate_present,
    "acceptance_criteria_required": _acceptance_criteria_required,
    "requirements_verifiable": _requirements_verifiable,
    "traceability_table_present": _traceability_table_present,
    "implementation_handoff_typed": _implementation_handoff_typed,
    "technical_spec_contract_present": _technical_spec_contract_present,
    "writable_scope_bounded": _writable_scope_bounded,
    "verification_commands_allowlisted": _verification_commands_allowlisted,
    "plan_has_patch_intent": _plan_has_patch_intent,
    "executor_handoff_present": _executor_handoff_present,
    "rollback_policy_present": _rollback_policy_present,
    "contract_test_matrix_required": _contract_test_matrix_required,
    "negative_tests_required": _negative_tests_required,
    "external_calls_faked_by_default": _external_calls_faked_by_default,
    "negative_tests_present": _negative_tests_present,
    "contract_matrix_targets_candidate": _contract_matrix_targets_candidate,
    "verification_is_project_scoped": _verification_is_project_scoped,
    "scope_preserved": _scope_preserved,
    "contract_violations_checked": _contract_violations_checked,
    "promotion_requires_human_review": _promotion_requires_human_review,
    "recommendation_explicit": _recommendation_explicit,
    "risks_have_mitigation": _risks_have_mitigation,
    "review_target_matches_plan": _review_target_matches_plan,
    "evidence_refs_required": _evidence_refs_required,
    "source_attribution_required": _source_attribution_required,
    "kb_admission_policy_required": _kb_admission_policy_required,
    "candidate_has_evidence": _candidate_has_evidence,
    "facts_and_judgments_separated": _facts_and_judgments_separated,
    "approval_gates_declared": _approval_gates_declared,
}
