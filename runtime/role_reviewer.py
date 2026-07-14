"""Reviewer role skill."""

from __future__ import annotations

from typing import Any

from .role_skill_common import now_iso


def run_reviewer_skill(
    *,
    technical_spec: dict[str, Any],
    implementation_plan: dict[str, Any],
    test_plan: dict[str, Any],
    test_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    findings = _findings(technical_spec, implementation_plan, test_plan, test_result or {})
    conformance = _conformance_checks(technical_spec, implementation_plan, test_plan, test_result or {})
    if any(not item["passed"] for item in conformance):
        findings.append(_finding("conformance_check_failed", "high", "Deterministic conformance checks failed."))
    risks = _risk_assessment(implementation_plan, test_plan, findings)
    review_target = _review_target(implementation_plan, test_plan)
    return {
        "artifact_type": "ReviewFindings",
        "role": "reviewer",
        "status": "ok",
        "created_at": now_iso(),
        "source_artifacts": [
            {"type": technical_spec.get("artifact_type"), "role": technical_spec.get("role")},
            {"type": implementation_plan.get("artifact_type"), "role": implementation_plan.get("role")},
            {"type": test_plan.get("artifact_type"), "role": test_plan.get("role")},
        ],
        "review_target": review_target,
        "coverage_assessment": _coverage_assessment(implementation_plan, test_plan, review_target),
        "conformance_checks": conformance,
        "conformance_status": "passed" if all(item["passed"] for item in conformance) else "failed",
        "findings": findings,
        "risk_assessment": risks,
        "contract_violations": _contract_violations(technical_spec, implementation_plan, test_plan),
        "architecture_drift": _architecture_drift(technical_spec, implementation_plan),
        "rework_tasks": _rework_tasks(findings, risks),
        "recommendation": _recommendation(findings, risks),
        "forbidden_actions_observed": [],
        "forbidden_actions_enforced": ["write_code", "edit_registry", "execute_pipeline", "promote_candidate"],
    }


def _findings(
    technical_spec: dict[str, Any],
    implementation_plan: dict[str, Any],
    test_plan: dict[str, Any],
    test_result: dict[str, Any],
) -> list[dict[str, Any]]:
    findings = []
    if not implementation_plan.get("patch_scope"):
        findings.append(_finding("missing_patch_scope", "high", "ImplementationPlan has no patch scope."))
    target = str(dict(implementation_plan.get("implementation_target", {})).get("candidate") or "")
    tested_target = str(dict(test_plan.get("test_target", {})).get("candidate") or "")
    if dict(implementation_plan.get("implementation_target", {})).get("status") == "blocked_no_safe_candidate":
        findings.append(_finding("blocked_no_safe_candidate", "info", "Implementation is blocked until source-specific extraction evidence exists."))
        return findings
    if target and tested_target != target:
        findings.append(_finding("test_target_mismatch", "high", "TestPlan target does not match ImplementationPlan target."))
    if target and not _target_is_covered(test_plan, target):
        findings.append(_finding("target_not_tested", "high", "Selected implementation target is not covered by tests."))
    scope_issues = _scope_issues(implementation_plan, test_plan)
    findings.extend(scope_issues)
    if not test_plan.get("contract_test_matrix"):
        findings.append(_finding("missing_contract_test_matrix", "high", "TestPlan has no contract test matrix."))
    if not test_plan.get("negative_tests"):
        findings.append(_finding("missing_negative_tests", "medium", "TestPlan has no negative tests."))
    if not technical_spec.get("acceptance_criteria"):
        findings.append(_finding("missing_acceptance_criteria", "high", "TechnicalSpec has no acceptance criteria."))
    if test_result and test_result.get("status") not in {"ok", "passed", "success"}:
        findings.append(_finding("test_result_not_green", "high", f"Test result status is {test_result.get('status')}."))
    if not findings:
        findings.append(_finding("no_blocking_findings", "info", "No blocking review findings detected."))
    return findings


def _risk_assessment(
    implementation_plan: dict[str, Any],
    test_plan: dict[str, Any],
    findings: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    risks = []
    for item in test_plan.get("regression_risks", [])[:6]:
        risks.append(
            {
                "target": item.get("target"),
                "severity": "medium",
                "risk": item.get("risk"),
                "mitigation": item.get("mitigation"),
            }
        )
    if "edit_registry" in implementation_plan.get("forbidden_actions_observed", []):
        risks.append({"target": "registry", "severity": "high", "risk": "Forbidden registry mutation observed."})
    if any(item.get("severity") == "high" for item in findings):
        risks.append({"target": "review", "severity": "high", "risk": "Blocking review findings must be resolved."})
    return risks or [{"target": "review", "severity": "low", "risk": "No material residual risk detected."}]


def _contract_violations(
    technical_spec: dict[str, Any],
    implementation_plan: dict[str, Any],
    test_plan: dict[str, Any],
) -> list[dict[str, Any]]:
    violations = []
    spec_acceptance = {item.get("id") for item in technical_spec.get("acceptance_criteria", [])}
    tested = {item.get("acceptance_id") for item in test_plan.get("acceptance_tests", [])}
    missing = sorted(str(item) for item in spec_acceptance - tested if item)
    if missing:
        violations.append({"code": "acceptance_not_tested", "missing_acceptance_ids": missing})
    if not implementation_plan.get("rollback_plan"):
        violations.append({"code": "missing_rollback_plan"})
    target = str(dict(implementation_plan.get("implementation_target", {})).get("candidate") or "")
    if target and str(dict(test_plan.get("test_target", {})).get("candidate") or "") != target:
        violations.append({"code": "test_target_mismatch", "target": target})
    if target and not _target_is_covered(test_plan, target):
        violations.append({"code": "implementation_target_not_covered", "target": target})
    violations.extend(_scope_violations(implementation_plan, test_plan))
    binding = dict(implementation_plan.get("contract_binding", {}))
    matrix = list(test_plan.get("contract_test_matrix", []))
    input_fields = {str(key) for key in dict(binding.get("input_contract", {}))}
    output_fields = {str(key) for key in dict(binding.get("output_contract", {}))}
    matrix_inputs = {str(row.get("field")) for row in matrix if row.get("direction") == "input"}
    matrix_outputs = {str(row.get("field")) for row in matrix if row.get("direction") == "output"}
    if input_fields - matrix_inputs:
        violations.append({"code": "input_contract_not_covered", "missing_fields": sorted(input_fields - matrix_inputs)})
    if output_fields - matrix_outputs:
        violations.append({"code": "output_contract_not_covered", "missing_fields": sorted(output_fields - matrix_outputs)})
    return violations


def _conformance_checks(
    technical_spec: dict[str, Any],
    implementation_plan: dict[str, Any],
    test_plan: dict[str, Any],
    test_result: dict[str, Any],
) -> list[dict[str, Any]]:
    forbidden_observed = (
        list(technical_spec.get("forbidden_actions_observed", []))
        + list(implementation_plan.get("forbidden_actions_observed", []))
        + list(test_plan.get("forbidden_actions_observed", []))
    )
    spec_acceptance = {str(item.get("id")) for item in technical_spec.get("acceptance_criteria", []) if item.get("id")}
    tested_acceptance = {str(item.get("acceptance_id")) for item in test_plan.get("acceptance_tests", []) if item.get("acceptance_id")}
    executable = dict(test_plan.get("executable_acceptance", {}))
    obligations = list(executable.get("obligations", []))
    return [
        _check(
            "artifact_chain_present",
            technical_spec.get("artifact_type") == "TechnicalSpec"
            and implementation_plan.get("artifact_type") == "ImplementationPlan"
            and test_plan.get("artifact_type") == "TestPlan",
            "TechnicalSpec, ImplementationPlan and TestPlan must be present.",
        ),
        _check(
            "traceability_present",
            bool(technical_spec.get("traceability_table")) and bool(implementation_plan.get("acceptance_mapping")),
            "Spec traceability and implementation acceptance mapping must exist.",
        ),
        _check(
            "acceptance_covered",
            bool(spec_acceptance) and spec_acceptance <= tested_acceptance,
            "Every TechnicalSpec acceptance criterion must have a TestPlan acceptance test.",
            {"missing": sorted(spec_acceptance - tested_acceptance)},
        ),
        _check(
            "executable_acceptance_ready",
            executable.get("status") == "ready" and bool(obligations),
            "Tester must publish executable acceptance obligations.",
            {"obligation_count": len(obligations)},
        ),
        _check(
            "scope_constrained",
            not _scope_violations(implementation_plan, test_plan),
            "Writable scope and read-only evidence scope must remain constrained.",
        ),
        _check(
            "forbidden_actions_clean",
            not forbidden_observed,
            "No role artifact may report forbidden actions.",
            {"observed": forbidden_observed},
        ),
        _check(
            "test_result_green_or_absent",
            not test_result or test_result.get("status") in {"ok", "passed", "success"},
            "If TestResult is present, it must be green.",
            {"status": test_result.get("status")},
        ),
    ]


def _architecture_drift(technical_spec: dict[str, Any], implementation_plan: dict[str, Any]) -> list[dict[str, Any]]:
    patch_scope = set(implementation_plan.get("patch_scope", []))
    handoff_scope = set(dict(technical_spec.get("implementation_handoff", {})).get("patch_scope", []))
    extra = sorted(patch_scope - handoff_scope)
    if extra:
        return [{"code": "patch_scope_expanded", "extra_scope": extra}]
    spec_candidate = str(dict(technical_spec.get("extraction_contract", {})).get("candidate") or "")
    plan_candidate = str(dict(implementation_plan.get("implementation_target", {})).get("candidate") or "")
    if spec_candidate and plan_candidate != spec_candidate:
        return [{"code": "implementation_target_drift", "expected": spec_candidate, "actual": plan_candidate}]
    writable_scope = set(str(item) for item in implementation_plan.get("writable_scope", []))
    if plan_candidate and writable_scope and writable_scope != {plan_candidate}:
        return [{"code": "writable_scope_expanded", "expected": [plan_candidate], "actual": sorted(writable_scope)}]
    return []


def _rework_tasks(findings: list[dict[str, Any]], risks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    tasks = []
    for index, item in enumerate([*findings, *risks], start=1):
        if item.get("severity") not in {"high", "medium"}:
            continue
        tasks.append(
            {
                "id": f"REWORK-{index:03d}",
                "source": item.get("code") or item.get("target"),
                "action": item.get("description") or item.get("risk"),
            }
        )
    return tasks


def _recommendation(findings: list[dict[str, Any]], risks: list[dict[str, Any]]) -> str:
    if any(item.get("severity") == "high" for item in [*findings, *risks]):
        return "request_rework"
    if any(item.get("severity") == "medium" for item in [*findings, *risks]):
        return "approve_with_risks"
    return "approve"


def _finding(code: str, severity: str, description: str) -> dict[str, str]:
    return {"code": code, "severity": severity, "description": description}


def _check(code: str, passed: bool, description: str, detail: dict[str, Any] | None = None) -> dict[str, Any]:
    row = {"code": code, "passed": bool(passed), "description": description}
    if detail:
        row["detail"] = detail
    return row


def _review_target(implementation_plan: dict[str, Any], test_plan: dict[str, Any]) -> dict[str, Any]:
    implementation_target = dict(implementation_plan.get("implementation_target", {}))
    test_target = dict(test_plan.get("test_target", {}))
    target = str(implementation_target.get("candidate") or test_target.get("candidate") or "")
    return {
        "candidate": target,
        "implementation_target": implementation_target.get("candidate"),
        "test_target": test_target.get("candidate"),
        "binding_status": dict(implementation_plan.get("contract_binding", {})).get("binding_status"),
        "writable_scope": list(implementation_plan.get("writable_scope", [])),
    }


def _coverage_assessment(
    implementation_plan: dict[str, Any],
    test_plan: dict[str, Any],
    review_target: dict[str, Any],
) -> dict[str, Any]:
    target = str(review_target.get("candidate") or "")
    binding = dict(implementation_plan.get("contract_binding", {}))
    matrix = list(test_plan.get("contract_test_matrix", []))
    strategy = dict(test_plan.get("test_strategy", {}))
    return {
        "target": target,
        "target_covered": _target_is_covered(test_plan, target),
        "writable_scope": list(implementation_plan.get("writable_scope", [])),
        "test_writable_scope": list(strategy.get("writable_scope", [])),
        "evidence_scope": list(implementation_plan.get("evidence_scope", [])),
        "scope_preserved": not _scope_violations(implementation_plan, test_plan),
        "input_contract_fields": sorted(str(key) for key in dict(binding.get("input_contract", {}))),
        "output_contract_fields": sorted(str(key) for key in dict(binding.get("output_contract", {}))),
        "contract_matrix_rows": len(matrix),
        "negative_test_count": len(test_plan.get("negative_tests", [])),
    }


def _target_is_covered(test_plan: dict[str, Any], target: str) -> bool:
    if not target:
        return False
    rows = [
        *list(test_plan.get("acceptance_tests", [])),
        *list(test_plan.get("negative_tests", [])),
        *list(test_plan.get("contract_test_matrix", [])),
        *list(test_plan.get("regression_risks", [])),
    ]
    return any(isinstance(row, dict) and row.get("target") == target for row in rows)


def _scope_issues(implementation_plan: dict[str, Any], test_plan: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        _finding(item["code"], "high", item["description"])
        for item in _scope_violations(implementation_plan, test_plan)
    ]


def _scope_violations(implementation_plan: dict[str, Any], test_plan: dict[str, Any]) -> list[dict[str, Any]]:
    target = str(dict(implementation_plan.get("implementation_target", {})).get("candidate") or "")
    writable = [str(item) for item in implementation_plan.get("writable_scope", []) if item]
    strategy = dict(test_plan.get("test_strategy", {}))
    test_writable = [str(item) for item in strategy.get("writable_scope", []) if item]
    read_only = [str(item) for item in strategy.get("read_only_context", []) if item]
    evidence = [str(item) for item in implementation_plan.get("evidence_scope", []) if item]
    violations = []
    if target and writable and writable != [target]:
        violations.append(
            {
                "code": "implementation_writable_scope_expanded",
                "description": "ImplementationPlan writable_scope must contain only the selected target.",
                "expected": [target],
                "actual": writable,
            }
        )
    if writable and test_writable != writable:
        violations.append(
            {
                "code": "test_writable_scope_mismatch",
                "description": "TestPlan writable_scope must match ImplementationPlan writable_scope.",
                "expected": writable,
                "actual": test_writable,
            }
        )
    read_only_expected = sorted(item for item in evidence if item not in set(writable))
    if read_only_expected and sorted(read_only) != read_only_expected:
        violations.append(
            {
                "code": "read_only_context_mismatch",
                "description": "TestPlan must keep evidence-only scope separate from writable scope.",
                "expected": read_only_expected,
                "actual": sorted(read_only),
            }
        )
    return violations
