"""Digest-bound causal contract propagated through the project-development role chain."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any


SCHEMA_VERSION = "problem_outcome_contract.v1"
REQUIRED_CHECKS = (
    "issue_evidence_reproduced_before_change",
    "selected_issue_resolved_or_reduced",
    "targeted_acceptance_passed",
    "regression_suite_passed",
    "source_scope_preserved",
)


def build_problem_outcome_contract(
    issue: dict[str, Any], option: dict[str, Any]
) -> dict[str, Any]:
    targets = _strings(issue.get("affected_targets"))
    evidence = _strings(issue.get("evidence"))
    failures = [
        {
            "failure_signature": row.get("failure_signature"),
            "target": row.get("target"),
            "failing_nodeids": _strings(row.get("failing_nodeids")),
            "detail": row.get("detail"),
            "authority": row.get("authority"),
        }
        for row in issue.get("failure_evidence") or []
        if isinstance(row, dict)
    ]
    for failure in failures:
        target = str(failure.get("target") or "")
        signature = str(failure.get("failure_signature") or "")
        authority = str(failure.get("authority") or "failure_evidence")
        if target:
            evidence.append(f"{authority}:{target}")
        if signature:
            evidence.append(f"failure_signature:{signature}")
    evidence = list(dict.fromkeys(evidence))
    repair = dict(issue.get("repair_design") or {})
    status = "evidence_bound" if targets and evidence and failures else "hypothesis_only"
    contract = {
        "artifact_type": "ProblemOutcomeContract",
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "issue_id": issue.get("issue_id"),
        "rule_id": issue.get("rule_id"),
        "target": targets[0] if targets else None,
        "allowed_targets": targets,
        "evidence_refs": evidence,
        "baseline_failures": failures,
        "selected_strategy": option.get("strategy"),
        "repair_design": {
            "status": repair.get("status"),
            "mechanism": repair.get("mechanism"),
            "mutation_contract": repair.get("mutation_contract"),
            "proposed_operator_id": repair.get("proposed_operator_id"),
        },
        "expected_outcome": (
            f"Resolve or measurably reduce {issue.get('rule_id')} without widening the evidence-bound scope"
        ),
        "required_checks": list(REQUIRED_CHECKS),
        "forbidden_success_substitutes": [
            "artifact_presence_only",
            "tests_started_without_result",
            "unverified_model_claim",
            "unrelated_green_tests",
        ],
        "authority": {
            "source": "ProjectDevelopmentDecision",
            "execution_authorized": False,
            "source_mutation_authorized": False,
        },
    }
    contract["contract_digest"] = _digest(contract)
    return contract


def propagate_problem_outcome_contract(*artifacts: dict[str, Any]) -> dict[str, Any]:
    contracts = [
        dict(artifact.get("problem_outcome_contract") or {})
        for artifact in artifacts
        if artifact.get("problem_outcome_contract")
    ]
    if not contracts:
        return {}
    errors = [error for contract in contracts for error in validate_problem_outcome_contract(contract)]
    digests = {str(contract.get("contract_digest") or "") for contract in contracts}
    if len(digests) != 1:
        errors.append("contract_digest_chain_mismatch")
    if errors:
        raise ValueError("invalid problem outcome contract: " + ", ".join(sorted(set(errors))))
    return deepcopy(contracts[0])


def validate_problem_outcome_contract(contract: dict[str, Any]) -> list[str]:
    errors = []
    if contract.get("schema_version") != SCHEMA_VERSION:
        errors.append("schema_version")
    supplied = str(contract.get("contract_digest") or "")
    unsigned = {key: value for key, value in contract.items() if key != "contract_digest"}
    if supplied != _digest(unsigned):
        errors.append("contract_digest")
    if contract.get("status") == "evidence_bound":
        if not contract.get("target") or not contract.get("allowed_targets"):
            errors.append("target_scope")
        if not contract.get("evidence_refs") or not contract.get("baseline_failures"):
            errors.append("baseline_evidence")
        if set(REQUIRED_CHECKS) - set(_strings(contract.get("required_checks"))):
            errors.append("required_checks")
    authority = dict(contract.get("authority") or {})
    if authority.get("execution_authorized") is not False:
        errors.append("execution_authority")
    if authority.get("source_mutation_authorized") is not False:
        errors.append("mutation_authority")
    return sorted(set(errors))


def problem_outcome_conformance(
    technical_spec: dict[str, Any], implementation_plan: dict[str, Any], test_plan: dict[str, Any]
) -> dict[str, Any]:
    contract = propagate_problem_outcome_contract(technical_spec, implementation_plan, test_plan)
    if not contract:
        return {"status": "not_applicable", "checks": {}}
    target = str(contract.get("target") or "")
    plan_target = str(dict(implementation_plan.get("implementation_target") or {}).get("candidate") or "")
    test_target = str(dict(test_plan.get("test_target") or {}).get("candidate") or "")
    acceptance_ids = {
        str(row.get("acceptance_id") or row.get("id") or "")
        for row in test_plan.get("acceptance_tests") or []
        if isinstance(row, dict)
    }
    checks = {
        "target_preserved": _same_target(target, plan_target) and _same_target(target, test_target),
        "baseline_replay_planned": any(value.startswith("AC-FAILURE-REPLAY") for value in acceptance_ids),
        "regression_planned": "AC-FAILURE-REGRESSION" in acceptance_ids,
        "mutation_still_unauthorized": dict(contract.get("authority") or {}).get("source_mutation_authorized") is False,
    }
    return {
        "status": "passed" if all(checks.values()) else "failed",
        "contract_digest": contract["contract_digest"],
        "checks": checks,
        "failed_checks": [name for name, passed in checks.items() if not passed],
    }


def _same_target(expected: str, actual: str) -> bool:
    if not expected or not actual:
        return False
    return expected.replace("\\", "/") == actual.replace("\\", "/")


def _strings(values: Any) -> list[str]:
    if isinstance(values, (str, bytes)):
        return [str(values)] if values else []
    return [str(value) for value in values or [] if value]


def _digest(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()
