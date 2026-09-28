from __future__ import annotations

def _role_evidence(
    *,
    row: dict[str, Any],
    architecture_decision: dict[str, Any],
    technical_spec: dict[str, Any],
    plan: dict[str, Any],
    test_plan: dict[str, Any],
    test_result: dict[str, Any],
    control_result: dict[str, Any],
    passing_review: dict[str, Any],
    failing_review: dict[str, Any],
    transformation_quality: dict[str, Any],
    cli_evidence: dict[str, Any] | None,
    web_evidence: dict[str, Any] | None,
    provider_evidence: dict[str, Any] | None,
    stateful_evidence: dict[str, Any] | None,
    async_evidence: dict[str, Any] | None,
    io_evidence: dict[str, Any] | None,
    framework_evidence: dict[str, Any] | None,
    stub_admission: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    spec_quality = evaluate_technical_spec(technical_spec)
    implementation_quality = evaluate_implementation_plan(plan)
    test_plan_quality = evaluate_test_plan(test_plan)
    passing_review_quality = evaluate_review_findings(passing_review)
    failing_review_quality = evaluate_review_findings(failing_review)
    passing_acceptance = dict(test_result.get("executable_acceptance_result") or {})
    control_acceptance = dict(control_result.get("executable_acceptance_result") or {})
    control_summary = dict(control_acceptance.get("summary") or {})
    control_skip_reasons = {
        str(row.get("reason")) for row in control_summary.get("skipped_targets", [])
        if isinstance(row, dict)
    }
    failing_codes = {str(row.get("code")) for row in failing_review.get("findings", [])}
    checks = {
        "project_analyzer": {
            "source_project_identified": bool(row.get("project")),
            "source_target_bound": ".py:" in str(row.get("source_target") or ""),
            "source_callable_parsed": bool(row.get("source") and row.get("symbol")),
            "contract_profile_identified": bool(row.get("profile_id") and row.get("operator_id")),
            "source_lineage_bound": bool(row.get("source_lineage")),
        },
        "architect": {
            "bounded_option_selected": dict(architecture_decision.get("chosen_option") or {}).get("id") == "minimal_safe_extraction",
            "target_carried_to_brief": str(row.get("symbol") or "") in str(architecture_decision.get("spec_writer_brief") or ""),
            "source_context_bound": bool(architecture_decision.get("source_context")),
            "contract_profile_carried": str(row.get("profile_id") or "") in str(architecture_decision.get("spec_writer_brief") or ""),
            "traceability_present": bool(architecture_decision.get("traceability")),
        },
        "spec_writer": {
            "technical_spec_quality_passed": spec_quality.get("passed") is True,
            "implementation_delta_ready": dict(technical_spec.get("implementation_delta") or {}).get("status") == "ready",
            "extraction_target_bound": str(row.get("symbol") or "") in str(technical_spec.get("extraction_contract") or ""),
            "contract_profile_preserved": str(row.get("profile_id") or "") in str(technical_spec.get("extraction_contract") or ""),
            "implementation_handoff_bounded": bool(technical_spec.get("implementation_handoff")),
        },
        "implementer": {
            "plan_quality_passed": implementation_quality.get("passed") is True,
            "delta_ready": transformation_quality.get("delta_status") == "ready",
            "patch_prepared": transformation_quality.get("checks", {}).get("patch_prepared") is True,
            "transform_matches_contract": transformation_quality.get("checks", {}).get("transform_matches") is True,
            "verified_candidate_completed": transformation_quality.get("checks", {}).get("executor_completed") is True,
            "sandbox_source_preserved": transformation_quality.get("checks", {}).get("source_unchanged") is True,
            "generated_function_stubs_absent": stub_admission.get("status") == "passed",
        },
        "tester": {
            "test_plan_quality_passed": test_plan_quality.get("passed") is True,
            "patched_candidate_accepted": passing_acceptance.get("status") == "passed",
            "identity_control_rejected": control_result.get("status") == "failed",
            "patched_signal_is_executable": dict(passing_acceptance.get("summary") or {}).get("signal_strength") == "executable_callable",
            "control_failure_is_oracle_backed": "positive_sample_execution_failed" in control_skip_reasons,
        },
        "reviewer": {
            "passing_review_quality_passed": passing_review_quality.get("passed") is True,
            "failing_review_quality_passed": failing_review_quality.get("passed") is True,
            "passing_candidate_not_reworked": passing_review.get("recommendation") in {"approve", "approve_with_risks"},
            "failing_control_requests_rework": failing_review.get("recommendation") == "request_rework",
            "failing_control_has_test_finding": "test_result_not_green" in failing_codes,
        },
    }
    if cli_evidence:
        checks["implementer"]["cli_behavior_changed"] = (
            cli_evidence["patched"]["status"] == "passed"
            and cli_evidence["identity_control"]["status"] == "failed"
        )
        checks["tester"].update({
            "patched_cli_contract_passed": cli_evidence["patched"]["status"] == "passed",
            "identity_cli_contract_rejected": cli_evidence["identity_control"]["status"] == "failed",
        })
    if web_evidence:
        checks["implementer"]["http_behavior_changed"] = (
            web_evidence["patched"]["status"] == "passed"
            and web_evidence["identity_control"]["status"] == "failed"
        )
        checks["tester"].update({
            "patched_http_contract_passed": web_evidence["patched"]["status"] == "passed",
            "identity_http_contract_rejected": web_evidence["identity_control"]["status"] == "failed",
            "http_invalid_request_controlled": (
                web_evidence["patched"].get("invalid_status_code") == 400
                and "Traceback" not in str(web_evidence["patched"].get("invalid_body") or "")
            ),
        })
    if provider_evidence:
        checks["implementer"]["provider_behavior_changed"] = (
            provider_evidence["patched"]["status"] == "passed"
            and provider_evidence["identity_control"]["status"] == "failed"
        )
        checks["tester"].update({
            "patched_provider_contract_passed": provider_evidence["patched"]["status"] == "passed",
            "identity_provider_contract_rejected": provider_evidence["identity_control"]["status"] == "failed",
            "provider_failure_controlled": (
                provider_evidence["patched"].get("invalid_returncode") == 2
                and "Traceback" not in str(
                    provider_evidence["patched"].get("invalid_stderr_tail") or ""
                )
            ),
            "provider_call_observed": provider_evidence["patched"].get("call_count") == 1,
        })
    if stateful_evidence:
        checks["implementer"]["persisted_behavior_changed"] = (
            stateful_evidence["patched"]["status"] == "passed"
            and stateful_evidence["identity_control"]["status"] == "failed"
        )
        checks["tester"].update({
            "patched_state_contract_passed": stateful_evidence["patched"]["status"] == "passed",
            "identity_state_contract_rejected": stateful_evidence["identity_control"]["status"] == "failed",
            "state_failure_rolled_back": stateful_evidence["patched"].get("invalid_row_count") == 0,
            "persisted_value_observed": stateful_evidence["patched"].get("row_count") == 1,
        })
    if async_evidence:
        checks["implementer"]["async_behavior_changed"] = (
            async_evidence["patched"]["status"] == "passed"
            and async_evidence["identity_control"]["status"] == "failed"
        )
        checks["tester"].update({
            "patched_async_contract_passed": async_evidence["patched"]["status"] == "passed",
            "identity_async_contract_rejected": async_evidence["identity_control"]["status"] == "failed",
            "async_timeout_controlled": async_evidence["patched"].get("timeout_returncode") == 2,
            "async_task_observed": async_evidence["patched"].get("task_count") == 1,
        })
    if io_evidence:
        checks["implementer"]["external_io_behavior_changed"] = (
            io_evidence["patched"]["status"] == "passed"
            and io_evidence["identity_control"]["status"] == "failed"
        )
        checks["tester"].update({
            "patched_io_contract_passed": io_evidence["patched"]["status"] == "passed",
            "identity_io_contract_rejected": io_evidence["identity_control"]["status"] == "failed",
            "io_failure_controlled": io_evidence["patched"].get("invalid_returncode") == 2,
            "io_operation_observed": io_evidence["patched"].get("operation_count") == 1,
        })
    if framework_evidence:
        checks["implementer"]["framework_behavior_changed"] = (
            framework_evidence["patched"]["status"] == "passed"
            and framework_evidence["identity_control"]["status"] == "failed"
        )
        checks["tester"].update({
            "patched_framework_contract_passed": framework_evidence["patched"]["status"] == "passed",
            "identity_framework_contract_rejected": framework_evidence["identity_control"]["status"] == "failed",
            "framework_failure_controlled": framework_evidence["patched"].get("invalid_returncode") == 2,
            "framework_effect_observed": framework_evidence["patched"].get("effect_count") == 1,
        })
    return {
        role: {
            "score": round(10.0 * sum(role_checks.values()) / len(role_checks), 2),
            "checks": role_checks,
        }
        for role, role_checks in checks.items()
    }

