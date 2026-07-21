"""Generic TestPlan artifact builder."""

from __future__ import annotations

from typing import Any

from .role_skill_common import now_iso


def build_test_plan(
    *,
    technical_spec: dict[str, Any],
    implementation_plan: dict[str, Any],
    role_id: str = "tester",
    next_role_id: str = "reviewer",
) -> dict[str, Any]:
    acceptance = list(technical_spec.get("acceptance_criteria", []))
    verification = list(implementation_plan.get("verification_commands", []))
    patch_scope = list(implementation_plan.get("patch_scope", []))
    evidence_scope = list(implementation_plan.get("evidence_scope", patch_scope))
    writable_scope = list(implementation_plan.get("writable_scope", []))
    implementation_target = dict(implementation_plan.get("implementation_target", {}))
    contract_binding = dict(implementation_plan.get("contract_binding", {}))
    target = _target_name(implementation_target, patch_scope)
    return {
        "artifact_type": "TestPlan",
        "role": role_id,
        "status": "ok",
        "created_at": now_iso(),
        "source_artifacts": [
            {"type": technical_spec.get("artifact_type"), "role": technical_spec.get("role")},
            {"type": implementation_plan.get("artifact_type"), "role": implementation_plan.get("role")},
        ],
        "test_target": _test_target(implementation_target, contract_binding, target),
        "contract_test_matrix": _contract_test_matrix(contract_binding, target),
        "test_strategy": _test_strategy(patch_scope, evidence_scope, writable_scope, target),
        "acceptance_tests": _acceptance_tests(acceptance, target),
        "executable_acceptance": _executable_acceptance(acceptance, contract_binding, target),
        "negative_tests": _negative_tests(target, contract_binding),
        "smoke_checklist": _smoke_checklist(verification),
        "regression_risks": _regression_risks(evidence_scope, writable_scope, technical_spec, target),
        "reproducibility": {
            "inputs": ["TechnicalSpec", "ImplementationPlan", "repository state"],
            "required_artifacts": ["test output", "acceptance report", "changed file list"],
        },
        "forbidden_actions_observed": [],
        "forbidden_actions_enforced": ["write_code", "edit_registry", "execute_pipeline", "promote_candidate"],
        "next_artifact": {
            "type": "ReviewFindings",
            "recommended_role": next_role_id,
            "reason": "test plan is ready for independent review after execution",
        },
    }


def _target_name(implementation_target: dict[str, Any], patch_scope: list[str]) -> str:
    if implementation_target.get("status") == "blocked_no_safe_candidate":
        return "blocked_no_safe_candidate"
    return str(implementation_target.get("candidate") or (patch_scope[0] if patch_scope else "planned capability"))


def _test_target(
    implementation_target: dict[str, Any],
    contract_binding: dict[str, Any],
    target: str,
) -> dict[str, Any]:
    return {
        "candidate": target,
        "source": implementation_target.get("source_contract"),
        "binding_status": contract_binding.get("binding_status"),
        "input_contract": contract_binding.get("input_contract", {}),
        "output_contract": contract_binding.get("output_contract", {}),
    }


def _contract_test_matrix(contract_binding: dict[str, Any], target: str) -> list[dict[str, Any]]:
    input_contract = dict(contract_binding.get("input_contract", {}))
    output_contract = dict(contract_binding.get("output_contract", {}))
    rows = []
    for name, type_name in input_contract.items():
        rows.append(
            {
                "id": f"CONTRACT-IN-{len(rows) + 1:03d}",
                "target": target,
                "direction": "input",
                "field": name,
                "type": type_name,
                "expectation": "accepted when valid and rejected when missing or malformed",
            }
        )
    for name, type_name in output_contract.items():
        rows.append(
            {
                "id": f"CONTRACT-OUT-{len(rows) + 1:03d}",
                "target": target,
                "direction": "output",
                "field": name,
                "type": type_name,
                "expectation": "result shape matches TechnicalSpec output contract",
            }
        )
    return rows


def _test_strategy(
    patch_scope: list[str],
    evidence_scope: list[str],
    writable_scope: list[str],
    target: str,
) -> dict[str, Any]:
    return {
        "target": target,
        "scope": writable_scope or [target],
        "writable_scope": writable_scope or [target],
        "evidence_scope": evidence_scope or patch_scope,
        "read_only_context": [item for item in evidence_scope if item not in (writable_scope or [target])],
        "levels": ["contract", "negative", "regression", "acceptance"],
        "principle": "verify writable_scope against the TechnicalSpec without turning evidence_scope into write scope",
    }


def _acceptance_tests(acceptance: list[dict[str, Any]], target: str) -> list[dict[str, Any]]:
    tests = []
    for index, item in enumerate(acceptance, start=1):
        tests.append(
            {
                "id": f"TEST-AC-{index:03d}",
                "target": target,
                "acceptance_id": item.get("id"),
                "criterion": item.get("criterion"),
                "method": item.get("verification") or "pytest or review checklist",
                "execution_mode": "executable_or_manual_review" if index <= 10 else "review_checklist",
            }
        )
    return tests


def _executable_acceptance(
    acceptance: list[dict[str, Any]],
    contract_binding: dict[str, Any],
    target: str,
) -> dict[str, Any]:
    input_contract = dict(contract_binding.get("input_contract", {}))
    output_contract = dict(contract_binding.get("output_contract", {}))
    obligations = []
    for index, item in enumerate(acceptance[:10], start=1):
        acceptance_id = str(item.get("id") or f"AC-{index:03d}")
        obligations.append(
            {
                "id": f"OBL-{index:03d}",
                "acceptance_id": acceptance_id,
                "target": target,
                "kind": "positive_contract_case",
                "given": _sample_payload(input_contract),
                "expect": _expected_shape(output_contract),
                "oracle": "output_schema_and_acceptance_criterion",
                "source_criterion": item.get("criterion"),
            }
        )
    if input_contract:
        obligations.append(
            {
                "id": f"OBL-{len(obligations) + 1:03d}",
                "acceptance_id": "contract_negative_missing_input",
                "target": target,
                "kind": "malformed_input_case",
                "given": {},
                "expect": {"error": "controlled_validation_error"},
                "oracle": "missing_required_input_rejected",
            }
        )
    obligations.append(
        {
            "id": f"OBL-{len(obligations) + 1:03d}",
            "acceptance_id": "side_effect_boundary",
            "target": target,
            "kind": "side_effect_scope_case",
            "given": {"declared_scope": "writable_scope_only"},
            "expect": {"no_writes_outside_declared_scope": True},
            "oracle": "changed_file_list_is_subset_of_writable_scope",
        }
    )
    return {
        "status": "ready" if obligations else "empty",
        "format": "executable_acceptance_obligations_v0.1",
        "can_generate_scaffold": bool(obligations),
        "obligations": obligations,
    }


def _negative_tests(target: str, contract_binding: dict[str, Any]) -> list[dict[str, Any]]:
    input_fields = list(dict(contract_binding.get("input_contract", {})))
    first_field = input_fields[0] if input_fields else "required input"
    return [
        {
            "id": "TEST-NEG-001",
            "target": target,
            "case": f"missing or malformed {first_field} is rejected with controlled error",
        },
        {
            "id": "TEST-NEG-002",
            "target": target,
            "case": "unexpected side effect outside declared scope is not allowed",
        },
    ]


def _sample_payload(contract: dict[str, Any]) -> dict[str, Any]:
    return {str(name): _sample_value(str(type_name)) for name, type_name in contract.items()}


def _sample_value(type_name: str) -> Any:
    lowered = type_name.lower()
    if "int" in lowered or "number" in lowered:
        return 1
    if "bool" in lowered:
        return True
    if "list" in lowered or "array" in lowered:
        return []
    if "dict" in lowered or "object" in lowered:
        return {}
    return "sample"


def _expected_shape(contract: dict[str, Any]) -> dict[str, Any]:
    return {str(name): str(type_name) for name, type_name in contract.items()} or {"result": "declared_output"}


def _smoke_checklist(commands: list[str]) -> list[dict[str, Any]]:
    return [{"id": f"SMOKE-{index:03d}", "command": command} for index, command in enumerate(commands, start=1)]


def _regression_risks(
    evidence_scope: list[str],
    writable_scope: list[str],
    technical_spec: dict[str, Any],
    target: str,
) -> list[dict[str, Any]]:
    risks = []
    risks.append(
        {
            "target": target,
            "risk": "contract drift for selected implementation target",
            "mitigation": "contract matrix and acceptance tests must cover input/output binding",
        }
    )
    writable = set(writable_scope or [target])
    for item in evidence_scope[:5]:
        if item in writable:
            continue
        risks.append(
            {
                "target": item,
                "risk": "read-only evidence scope accidentally becomes implementation scope",
                "mitigation": "review changed files against writable_scope before execution",
            }
        )
    if technical_spec.get("non_goals"):
        risks.append(
            {
                "target": "scope",
                "risk": "implementation expands beyond non-goals",
                "mitigation": "review changed files against TechnicalSpec non-goals",
            }
        )
    return risks

