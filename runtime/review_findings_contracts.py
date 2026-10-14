from __future__ import annotations

from typing import Any

from .review_findings_common import blocked_handoff, finding, target_is_covered


def contract_violations(
    technical_spec: dict[str, Any],
    implementation_plan: dict[str, Any],
    test_plan: dict[str, Any],
) -> list[dict[str, Any]]:
    if blocked_handoff(implementation_plan, test_plan):
        return [] if test_plan.get("status") == "blocked_no_safe_candidate" else [{"code": "blocked_handoff_not_preserved"}]
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
    if target and not target_is_covered(test_plan, target):
        violations.append({"code": "implementation_target_not_covered", "target": target})
    violations.extend(scope_violations(implementation_plan, test_plan))
    _append_contract_matrix_violations(violations, implementation_plan, test_plan)
    unmodeled_effects = unmodeled_source_effects(technical_spec)
    if unmodeled_effects:
        violations.append({"code": "source_effect_contract_mismatch", "unmodeled_effects": unmodeled_effects})
    return violations


def _append_contract_matrix_violations(
    violations: list[dict[str, Any]],
    implementation_plan: dict[str, Any],
    test_plan: dict[str, Any],
) -> None:
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


def architecture_drift(
    technical_spec: dict[str, Any],
    implementation_plan: dict[str, Any],
) -> list[dict[str, Any]]:
    target = dict(implementation_plan.get("implementation_target", {}))
    if target.get("status") == "blocked_no_safe_candidate":
        spec_candidate = str(dict(technical_spec.get("extraction_contract", {})).get("candidate") or "")
        rejected = str(target.get("rejected_candidate") or "")
        return [] if not spec_candidate or rejected == spec_candidate else [{"code": "blocked_target_drift"}]
    patch_scope = set(implementation_plan.get("patch_scope", []))
    handoff_scope = set(dict(technical_spec.get("implementation_handoff", {})).get("patch_scope", []))
    extra = sorted(patch_scope - handoff_scope)
    if extra:
        return [{"code": "patch_scope_expanded", "extra_scope": extra}]
    spec_candidate = str(dict(technical_spec.get("extraction_contract", {})).get("candidate") or "")
    plan_candidate = str(target.get("candidate") or "")
    if spec_candidate and plan_candidate != spec_candidate:
        return [{"code": "implementation_target_drift", "expected": spec_candidate, "actual": plan_candidate}]
    writable_scope = set(str(item) for item in implementation_plan.get("writable_scope", []))
    if plan_candidate and writable_scope and writable_scope != {plan_candidate}:
        return [{"code": "writable_scope_expanded", "expected": [plan_candidate], "actual": sorted(writable_scope)}]
    return []


def unmodeled_source_effects(technical_spec: dict[str, Any]) -> list[str]:
    extraction = dict(technical_spec.get("extraction_contract") or {})
    observed = set(dict(extraction.get("structural_evidence") or {}).get("observed_side_effects") or [])
    declared = set(dict(extraction.get("side_effects") or {}).get("declared") or [])
    return sorted(str(effect) for effect in observed - declared)


def scope_issues(
    implementation_plan: dict[str, Any],
    test_plan: dict[str, Any],
) -> list[dict[str, Any]]:
    return [
        finding(item["code"], "high", item["description"])
        for item in scope_violations(implementation_plan, test_plan)
    ]


def scope_violations(
    implementation_plan: dict[str, Any],
    test_plan: dict[str, Any],
) -> list[dict[str, Any]]:
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
