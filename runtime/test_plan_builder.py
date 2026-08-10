"""Generic TestPlan artifact builder."""

from __future__ import annotations

from typing import Any

from .contract_transform_contract_profiles import profile_positive_case
from .executable_acceptance_policy import external_call_tokens, sample_value
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
    dependency_policy = _dependency_policy(technical_spec, implementation_plan, target)
    return {
        "artifact_type": "TestPlan",
        "role": role_id,
        "status": _plan_status(implementation_target),
        "created_at": now_iso(),
        "source_artifacts": [
            {"type": technical_spec.get("artifact_type"), "role": technical_spec.get("role")},
            {"type": implementation_plan.get("artifact_type"), "role": implementation_plan.get("role")},
        ],
        "test_target": _test_target(implementation_target, contract_binding, target),
        "contract_test_matrix": _contract_test_matrix(contract_binding, target),
        "test_strategy": _test_strategy(patch_scope, evidence_scope, writable_scope, target, dependency_policy),
        "dependency_policy": dependency_policy,
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


def _plan_status(implementation_target: dict[str, Any]) -> str:
    if implementation_target.get("status") == "blocked_no_safe_candidate":
        return "blocked_no_safe_candidate"
    return "ok"


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
    if contract_binding.get("binding_status") == "blocked_no_safe_candidate":
        return [
            {
                "id": "CONTRACT-BLOCK-001",
                "target": target,
                "direction": "blocked_handoff",
                "field": "safe_source_specific_candidate",
                "type": "required",
                "expectation": "implementation remains blocked until TechnicalSpec provides a source-backed candidate",
            },
            {
                "id": "CONTRACT-BLOCK-002",
                "target": target,
                "direction": "blocked_handoff",
                "field": "input_output_contract",
                "type": "required",
                "expectation": "no patch is planned until input and output contracts are bound to source evidence",
            },
        ]
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
                "expectation": _output_expectation(str(type_name)),
            }
        )
    return rows


def _test_strategy(
    patch_scope: list[str],
    evidence_scope: list[str],
    writable_scope: list[str],
    target: str,
    dependency_policy: dict[str, Any],
) -> dict[str, Any]:
    return {
        "target": target,
        "scope": writable_scope or [target],
        "writable_scope": writable_scope or [target],
        "evidence_scope": evidence_scope or patch_scope,
        "read_only_context": [item for item in evidence_scope if item not in (writable_scope or [target])],
        "levels": ["contract", "negative", "regression", "acceptance"],
        "principle": "verify writable_scope against the TechnicalSpec without turning evidence_scope into write scope",
        "external_calls": dependency_policy.get("external_calls", "none_detected"),
    }


def _dependency_policy(
    technical_spec: dict[str, Any],
    implementation_plan: dict[str, Any],
    target: str,
) -> dict[str, Any]:
    text = " ".join(
        [
            target,
            str(technical_spec.get("error_model", "")),
            str(technical_spec.get("interface_contracts", "")),
            str(implementation_plan.get("patch_scope", "")),
            str(implementation_plan.get("evidence_scope", "")),
        ]
    ).lower()
    external = any(token in text for token in external_call_tokens())
    if not external:
        return {"external_calls": "none_detected", "default_mode": "in_process_contract_tests"}
    return {
        "external_calls": "fake_by_default",
        "default_mode": "fake/mock/stub external HTTP, LLM, browser and subprocess calls in contract tests",
        "real_integration": "separate opt-in integration test only with explicit credentials/config and timeout budget",
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
    if contract_binding.get("binding_status") == "blocked_no_safe_candidate":
        return {
            "status": "blocked_no_safe_candidate",
            "format": "executable_acceptance_obligations_v0.1",
            "can_generate_scaffold": False,
            "obligations": [
                {
                    "id": "OBL-BLOCK-001",
                    "acceptance_id": "blocked_handoff_preserved",
                    "target": target,
                    "kind": "blocked_handoff_case",
                    "given": {"implementation_target_status": "blocked_no_safe_candidate"},
                    "expect": {"patch_generation_allowed": False},
                    "oracle": "executor_handoff_stays_blocked_until_source_candidate_exists",
                }
            ],
        }
    input_contract = dict(contract_binding.get("input_contract", {}))
    output_contract = dict(contract_binding.get("output_contract", {}))
    obligations = []
    profile_case = profile_positive_case(target=target, input_contract=input_contract, output_contract=output_contract)
    for index, item in enumerate(acceptance[:10], start=1):
        acceptance_id = str(item.get("id") or f"AC-{index:03d}")
        obligation = {
            "id": f"OBL-{index:03d}",
            "acceptance_id": acceptance_id,
            "target": target,
            "kind": "positive_contract_case",
            "given": _sample_payload(input_contract),
            "expect": _expected_shape(output_contract),
            "oracle": _positive_oracle(output_contract),
            "source_criterion": item.get("criterion"),
        }
        if profile_case:
            obligation.update(
                {
                    "given": dict(profile_case["given"]),
                    "expect": dict(profile_case["expect"]),
                    "oracle": str(profile_case["oracle"]),
                    "contract_profile": {
                        "id": str(profile_case["profile_id"]),
                        "operator_id": str(profile_case["operator_id"]),
                    },
                }
            )
        obligations.append(obligation)
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
    return {str(name): _sample_value(str(type_name), str(name)) for name, type_name in contract.items()}


def _sample_value(type_name: str, field_name: str = "") -> Any:
    return sample_value(type_name, field_name)


def _expected_shape(contract: dict[str, Any]) -> dict[str, Any]:
    if any(str(value).lower() == "voidsideeffect" for value in contract.values()):
        return {"completed": True}
    return {str(name): str(type_name) for name, type_name in contract.items()} or {"result": "declared_output"}


def _positive_oracle(contract: dict[str, Any]) -> str:
    if any(str(value).lower() == "voidsideeffect" for value in contract.values()):
        return "call_completes_and_side_effect_boundary_is_declared"
    return "output_schema_and_acceptance_criterion"


def _output_expectation(type_name: str) -> str:
    if type_name.lower() == "voidsideeffect":
        return "call completes without requiring a returned value; side-effect scope is checked separately"
    return "result shape matches TechnicalSpec output contract"


def _smoke_checklist(commands: list[str]) -> list[dict[str, Any]]:
    rows = [{"id": f"SMOKE-{index:03d}", "command": command} for index, command in enumerate(commands, start=1)]
    if rows and len(rows) < 3:
        rows.append({"id": f"SMOKE-{len(rows) + 1:03d}", "command": "python -m pytest tests -q --maxfail=1"})
    return rows


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

