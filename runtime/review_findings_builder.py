"""Generic ReviewFindings artifact builder."""

from __future__ import annotations

from typing import Any

from .review_findings_assessment import (
    findings as _findings,
    recommendation as _recommendation,
    rework_tasks as _rework_tasks,
    risk_assessment as _risk_assessment,
)
from .review_findings_common import (
    blocked_handoff as _blocked_handoff,
    check_row as _check,
    finding as _finding,
    nonzero as _nonzero,
    target_is_covered as _target_is_covered,
)
from .review_findings_conformance import (
    conformance_checks as _conformance_checks,
    test_result_has_failure_evidence as _test_result_has_failure_evidence,
)
from .review_findings_contracts import (
    architecture_drift as _architecture_drift,
    contract_violations as _contract_violations,
    scope_issues as _scope_issues,
    scope_violations as _scope_violations,
    unmodeled_source_effects as _unmodeled_source_effects,
)
from .review_findings_target import (
    coverage_assessment as _coverage_assessment,
    review_target as _review_target,
)
from .role_skill_common import now_iso


def build_review_findings(
    *,
    technical_spec: dict[str, Any],
    implementation_plan: dict[str, Any],
    test_plan: dict[str, Any],
    role_id: str = "reviewer",
    test_result: dict[str, Any] | None = None,
    executable_acceptance_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    acceptance_result = executable_acceptance_result or dict(
        (test_result or {}).get("executable_acceptance_result", {})
    )
    findings = _findings(technical_spec, implementation_plan, test_plan, test_result or {})
    conformance = _conformance_checks(
        technical_spec,
        implementation_plan,
        test_plan,
        test_result or {},
        acceptance_result,
    )
    if any(not item["passed"] for item in conformance):
        findings.append(_finding("conformance_check_failed", "high", "Deterministic conformance checks failed."))
    risks = _risk_assessment(
        implementation_plan,
        test_plan,
        findings,
        conformance_passed=all(item["passed"] for item in conformance),
        test_result_present=test_result is not None,
    )
    review_target = _review_target(implementation_plan, test_plan)
    recommendation = _recommendation(findings, risks)
    return {
        "artifact_type": "ReviewFindings",
        "role": role_id,
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
        "recommendation": recommendation,
        "promotion_policy": {
            "automatic_promotion_forbidden": True,
            "human_release_approval_required": True,
            "material_risk_decision_required": recommendation in {"approve_with_risks", "request_rework"},
        },
        "forbidden_actions_observed": [],
        "forbidden_actions_enforced": ["write_code", "edit_registry", "execute_pipeline", "promote_candidate"],
    }
