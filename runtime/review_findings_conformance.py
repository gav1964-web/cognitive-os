from __future__ import annotations

from typing import Any

from .review_findings_common import blocked_handoff, check_row
from .review_findings_contracts import scope_violations, unmodeled_source_effects
from .problem_outcome_contract import problem_outcome_conformance
from .native_failure_acceptance import FORMAT as NATIVE_FORMAT, native_coverage
from .narrow_type_evidence_binding import content_digest
from .upstream_causal_review import causal_comparison_checks


def conformance_checks(
    technical_spec: dict[str, Any],
    implementation_plan: dict[str, Any],
    test_plan: dict[str, Any],
    test_result: dict[str, Any],
    executable_acceptance_result: dict[str, Any],
) -> list[dict[str, Any]]:
    forbidden_observed = (
        list(technical_spec.get("forbidden_actions_observed", []))
        + list(implementation_plan.get("forbidden_actions_observed", []))
        + list(test_plan.get("forbidden_actions_observed", []))
    )
    spec_acceptance = {
        str(item.get("id"))
        for item in technical_spec.get("acceptance_criteria", [])
        if item.get("id")
    }
    tested_acceptance = {
        str(item.get("acceptance_id"))
        for item in test_plan.get("acceptance_tests", [])
        if item.get("acceptance_id")
    }
    executable = dict(test_plan.get("executable_acceptance", {}))
    obligations = list(executable.get("obligations", []))
    causal = problem_outcome_conformance(technical_spec, implementation_plan, test_plan)
    if blocked_handoff(implementation_plan, test_plan):
        rows = _blocked_handoff_checks(
            technical_spec,
            implementation_plan,
            test_plan,
            forbidden_observed,
        )
        rows.insert(1, _problem_outcome_check(causal))
        rows.extend(_upstream_task_checks(technical_spec, executable_acceptance_result))
        rows.extend(causal_comparison_checks(technical_spec, executable_acceptance_result))
        return rows
    return [
        _artifact_chain_check(technical_spec, implementation_plan, test_plan),
        _problem_outcome_check(causal),
        *_upstream_task_checks(technical_spec, executable_acceptance_result),
        *causal_comparison_checks(technical_spec, executable_acceptance_result),
        *_native_evidence_checks(technical_spec, executable, test_result, executable_acceptance_result),
        check_row(
            "traceability_present",
            bool(technical_spec.get("traceability_table")) and bool(implementation_plan.get("acceptance_mapping")),
            "Spec traceability and implementation acceptance mapping must exist.",
        ),
        check_row(
            "acceptance_covered",
            bool(spec_acceptance) and spec_acceptance <= tested_acceptance,
            "Every TechnicalSpec acceptance criterion must have a TestPlan acceptance test.",
            {"missing": sorted(spec_acceptance - tested_acceptance)},
        ),
        check_row(
            "executable_acceptance_ready",
            executable.get("status") == "ready" and bool(obligations),
            "Tester must publish executable acceptance obligations.",
            {"obligation_count": len(obligations)},
        ),
        check_row(
            "scope_constrained",
            not scope_violations(implementation_plan, test_plan),
            "Writable scope and read-only evidence scope must remain constrained.",
        ),
        check_row(
            "source_effects_declared",
            not unmodeled_source_effects(technical_spec),
            "Every source-observed side effect must be present in the extraction contract.",
            {"unmodeled_effects": unmodeled_source_effects(technical_spec)},
        ),
        check_row(
            "forbidden_actions_clean",
            not forbidden_observed,
            "No role artifact may report forbidden actions.",
            {"observed": forbidden_observed},
        ),
        check_row(
            "test_result_green_or_absent",
            not test_result or (
                test_result.get("status") in {"ok", "passed", "success"}
                and not test_result_has_failure_evidence(test_result)
            ),
            "If TestResult is present, it must be green.",
            {"status": test_result.get("status")},
        ),
        check_row(
            "executable_acceptance_passed_or_absent",
            not executable_acceptance_result or executable_acceptance_result.get("status") == "passed",
            "If ExecutableAcceptanceResult is present, it must pass.",
            {"status": executable_acceptance_result.get("status")},
        ),
    ]


def _upstream_task_checks(spec: dict, acceptance: dict | None = None) -> list[dict]:
    if 'task_contract' not in spec:
        return []
    if spec.get('requested_change'):
        from .upstream_requested_review import requested_change_checks
        return requested_change_checks(spec, acceptance or {})
    return [check_row('requested_change_design_verified', False,
        'Explicit task contracts currently support planning only; supplied requirements and examples do not validate an implementation design.',
        {'status': spec.get('task_handoff', {}).get('status')})]


def _native_evidence_checks(spec: dict, contract: dict, test_result: dict, acceptance: dict) -> list[dict]:
    if spec.get("contract_mode") != "failure_repair" and contract.get("format") != NATIVE_FORMAT:
        return []
    unsigned = {key: value for key, value in contract.items() if key != "contract_digest"}
    bound = (contract.get("format") == NATIVE_FORMAT
             and contract.get("contract_digest") == content_digest(unsigned))
    executed = bool(test_result or acceptance)
    if executed:
        bound = (bound and acceptance.get("format") == NATIVE_FORMAT
                 and acceptance.get("status") == "passed"
                 and acceptance.get("contract_digest") == contract.get("contract_digest")
                 and native_coverage(dict(acceptance.get("summary") or {}), {contract.get("target")}))
    native = dict(test_result.get("project_native_verification") or {})
    source_check = dict(test_result.get("post_regression_source_check") or {})
    accepted_digest = acceptance.get("patched_inventory_digest")
    regression = (not executed or (native.get("status") == "passed"
                  and dict(native.get("targeted_replay") or {}).get("status") == "passed"
                  and dict(native.get("regression_suite") or {}).get("status") == "passed"
                  and source_check.get("status") == "passed" and bool(accepted_digest)
                  and source_check.get("accepted_inventory_digest") == accepted_digest
                  and source_check.get("current_inventory_digest") == accepted_digest))
    return [
        check_row("native_acceptance_bound_to_plan", bound,
                  "Native result must match the TestPlan contract, target and all paired replay checks."),
        check_row("native_regression_complete", regression,
                  "Execution review requires native targeted and regression results; planning review remains separate."),
    ]


def _problem_outcome_check(causal: dict[str, Any]) -> dict[str, Any]:
    return check_row(
        "problem_outcome_contract_preserved",
        causal["status"] in {"not_applicable", "passed"},
        "Evidence-bound development must preserve target, baseline replay and regression obligations.",
        causal,
    )


def _blocked_handoff_checks(
    technical_spec: dict[str, Any],
    implementation_plan: dict[str, Any],
    test_plan: dict[str, Any],
    forbidden_observed: list[Any],
) -> list[dict[str, Any]]:
    return [
        _artifact_chain_check(technical_spec, implementation_plan, test_plan),
        check_row(
            "blocked_handoff_preserved",
            dict(implementation_plan.get("contract_binding", {})).get("binding_status")
            == "blocked_no_safe_candidate"
            and test_plan.get("status") == "blocked_no_safe_candidate",
            "Blocked TechnicalSpec handoff must stay blocked for Tester and Reviewer.",
        ),
        check_row(
            "blocked_matrix_present",
            bool(test_plan.get("contract_test_matrix")),
            "Tester must publish blocked-handoff verification rows.",
        ),
        check_row(
            "forbidden_actions_clean",
            not forbidden_observed,
            "No role artifact may report forbidden actions.",
            {"observed": forbidden_observed},
        ),
    ]


def _artifact_chain_check(
    technical_spec: dict[str, Any],
    implementation_plan: dict[str, Any],
    test_plan: dict[str, Any],
) -> dict[str, Any]:
    return check_row(
        "artifact_chain_present",
        technical_spec.get("artifact_type") == "TechnicalSpec"
        and implementation_plan.get("artifact_type") == "ImplementationPlan"
        and test_plan.get("artifact_type") == "TestPlan",
        "TechnicalSpec, ImplementationPlan and TestPlan must be present.",
    )


def test_result_has_failure_evidence(test_result: dict[str, Any]) -> bool:
    commands = list(test_result.get("commands") or test_result.get("command_results") or [])
    if any(
        isinstance(row, dict)
        and (row.get("status") == "failed" or _nonzero(row.get("exit_code", row.get("returncode"))))
        for row in commands
    ):
        return True
    summary = dict(test_result.get("summary") or {})
    if int(summary.get("failed") or 0) > 0:
        return True
    executable = dict(test_result.get("executable_acceptance_result") or {})
    return executable.get("status") == "failed"


def _nonzero(value: Any) -> bool:
    try:
        return value is not None and int(value) != 0
    except (TypeError, ValueError):
        return True
