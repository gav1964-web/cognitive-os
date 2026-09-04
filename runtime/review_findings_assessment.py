from __future__ import annotations

from typing import Any

from .review_findings_common import finding, target_is_covered
from .review_findings_contracts import scope_issues
from .review_findings_conformance import test_result_has_failure_evidence


def findings(
    technical_spec: dict[str, Any],
    implementation_plan: dict[str, Any],
    test_plan: dict[str, Any],
    test_result: dict[str, Any],
) -> list[dict[str, Any]]:
    rows = []
    if not implementation_plan.get("patch_scope"):
        rows.append(finding("missing_patch_scope", "high", "ImplementationPlan has no patch scope."))
    target = str(dict(implementation_plan.get("implementation_target", {})).get("candidate") or "")
    tested_target = str(dict(test_plan.get("test_target", {})).get("candidate") or "")
    if dict(implementation_plan.get("implementation_target", {})).get("status") == "blocked_no_safe_candidate":
        rows.append(finding("blocked_no_safe_candidate", "high", "Implementation is blocked until source-specific extraction evidence exists."))
        return rows
    if target and tested_target != target:
        rows.append(finding("test_target_mismatch", "high", "TestPlan target does not match ImplementationPlan target."))
    if target and not target_is_covered(test_plan, target):
        rows.append(finding("target_not_tested", "high", "Selected implementation target is not covered by tests."))
    rows.extend(scope_issues(implementation_plan, test_plan))
    if not test_plan.get("contract_test_matrix"):
        rows.append(finding("missing_contract_test_matrix", "high", "TestPlan has no contract test matrix."))
    if not test_plan.get("negative_tests"):
        rows.append(finding("missing_negative_tests", "medium", "TestPlan has no negative tests."))
    if not technical_spec.get("acceptance_criteria"):
        rows.append(finding("missing_acceptance_criteria", "high", "TechnicalSpec has no acceptance criteria."))
    if test_result and test_result.get("status") not in {"ok", "passed", "success"}:
        rows.append(finding("test_result_not_green", "high", f"Test result status is {test_result.get('status')}."))
    if test_result and test_result_has_failure_evidence(test_result):
        rows.append(finding("false_green_test_result", "high", "TestResult claims success but contains failure evidence."))
    if not rows:
        rows.append(finding("no_blocking_findings", "info", "No blocking review findings detected."))
    return rows


def risk_assessment(
    implementation_plan: dict[str, Any],
    test_plan: dict[str, Any],
    findings_rows: list[dict[str, Any]],
    *,
    conformance_passed: bool,
    test_result_present: bool,
) -> list[dict[str, Any]]:
    risks = []
    for item in test_plan.get("regression_risks", [])[:6]:
        risks.append(
            {
                "target": item.get("target"),
                "severity": "medium",
                "risk": item.get("risk"),
                "mitigation": item.get("mitigation"),
                "disposition": (
                    "controlled_by_verified_plan"
                    if conformance_passed and bool(item.get("mitigation"))
                    else "requires_human_review"
                ),
            }
        )
    if "edit_registry" in implementation_plan.get("forbidden_actions_observed", []):
        risks.append({
            "target": "registry",
            "severity": "high",
            "risk": "Forbidden registry mutation observed.",
            "mitigation": "revert the registry mutation and rerun the bounded review before promotion",
            "disposition": "requires_rework",
        })
    if any(item.get("severity") == "high" for item in findings_rows):
        risks.append({
            "target": "review",
            "severity": "high",
            "risk": "Blocking review findings must be resolved.",
            "mitigation": "complete the generated rework tasks and rerun Reviewer before promotion",
            "disposition": "requires_rework",
        })
    if not test_result_present:
        risks.append({
            "target": "execution",
            "severity": "medium",
            "risk": "Review is pre-execution; planned tests have not produced a TestResult.",
            "mitigation": "run the sandbox verification plan and return TestResult before release approval",
            "disposition": "requires_human_review",
        })
    return risks or [{
        "target": "review",
        "severity": "low",
        "risk": "No material residual risk detected.",
        "disposition": "controlled_by_verified_plan",
    }]


def rework_tasks(
    findings_rows: list[dict[str, Any]],
    risks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    tasks = []
    actionable = [
        item
        for item in [*findings_rows, *risks]
        if item.get("severity") == "high"
        or (item in findings_rows and item.get("severity") == "medium")
    ]
    for index, item in enumerate(actionable, start=1):
        if item.get("code") == "no_blocking_findings":
            continue
        tasks.append(
            {
                "id": f"REWORK-{index:03d}",
                "source": item.get("code") or item.get("target"),
                "action": item.get("description") or item.get("risk"),
            }
        )
    return tasks


def recommendation(findings_rows: list[dict[str, Any]], risks: list[dict[str, Any]]) -> str:
    if any(item.get("severity") == "high" for item in [*findings_rows, *risks]):
        return "request_rework"
    if any(item.get("severity") == "medium" for item in findings_rows):
        return "approve_with_risks"
    if any(
        item.get("severity") == "medium"
        and item.get("disposition") != "controlled_by_verified_plan"
        for item in risks
    ):
        return "approve_with_risks"
    return "approve"
