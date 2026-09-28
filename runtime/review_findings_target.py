from __future__ import annotations

from typing import Any

from .review_findings_common import target_is_covered
from .review_findings_contracts import scope_violations


def review_target(
    implementation_plan: dict[str, Any],
    test_plan: dict[str, Any],
) -> dict[str, Any]:
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


def coverage_assessment(
    implementation_plan: dict[str, Any],
    test_plan: dict[str, Any],
    target: dict[str, Any],
) -> dict[str, Any]:
    candidate = str(target.get("candidate") or "")
    binding = dict(implementation_plan.get("contract_binding", {}))
    matrix = list(test_plan.get("contract_test_matrix", []))
    strategy = dict(test_plan.get("test_strategy", {}))
    return {
        "target": candidate,
        "target_covered": target_is_covered(test_plan, candidate),
        "writable_scope": list(implementation_plan.get("writable_scope", [])),
        "test_writable_scope": list(strategy.get("writable_scope", [])),
        "evidence_scope": list(implementation_plan.get("evidence_scope", [])),
        "scope_preserved": not scope_violations(implementation_plan, test_plan),
        "input_contract_fields": sorted(str(key) for key in dict(binding.get("input_contract", {}))),
        "output_contract_fields": sorted(str(key) for key in dict(binding.get("output_contract", {}))),
        "contract_matrix_rows": len(matrix),
        "negative_test_count": len(test_plan.get("negative_tests", [])),
    }
