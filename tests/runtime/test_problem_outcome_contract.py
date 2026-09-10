from __future__ import annotations

import pytest

from runtime.problem_outcome_contract import (
    build_problem_outcome_contract,
    problem_outcome_conformance,
    propagate_problem_outcome_contract,
    validate_problem_outcome_contract,
)


def test_problem_outcome_contract_is_digest_bound_and_non_authorizing() -> None:
    contract = _contract()

    assert contract["status"] == "evidence_bound"
    assert contract["authority"]["execution_authorized"] is False
    assert validate_problem_outcome_contract(contract) == []

    contract["target"] = "src/other.py:wrong"
    assert validate_problem_outcome_contract(contract) == ["contract_digest"]


def test_propagation_rejects_role_chain_contract_drift() -> None:
    contract = _contract()
    changed = dict(contract)
    changed["contract_digest"] = "sha256:" + "0" * 64

    with pytest.raises(ValueError, match="contract_digest"):
        propagate_problem_outcome_contract(
            {"problem_outcome_contract": contract}, {"problem_outcome_contract": changed}
        )


def test_conformance_requires_targeted_replay_and_regression() -> None:
    contract = _contract()
    spec = {"problem_outcome_contract": contract}
    plan = {
        "problem_outcome_contract": contract,
        "implementation_target": {"candidate": "src/module.py:parse"},
    }
    test_plan = {
        "problem_outcome_contract": contract,
        "test_target": {"candidate": "src/module.py:parse"},
        "acceptance_tests": [
            {"acceptance_id": "AC-FAILURE-REPLAY-001"},
            {"acceptance_id": "AC-FAILURE-REGRESSION"},
        ],
    }

    assert problem_outcome_conformance(spec, plan, test_plan)["status"] == "passed"
    test_plan["acceptance_tests"].pop()
    assert problem_outcome_conformance(spec, plan, test_plan)["failed_checks"] == ["regression_planned"]


def test_scalar_contract_values_are_not_split_into_characters() -> None:
    contract = build_problem_outcome_contract(
        {
            "issue_id": "ISSUE-1",
            "rule_id": "weak_contracts",
            "affected_targets": "pkg/service.py:run",
            "evidence": "failing_contract_test:pkg/service.py:run",
            "failure_evidence": [{
                "target": "pkg/service.py:run",
                "failure_signature": "sig",
                "failing_nodeids": "tests/test_service.py::test_run",
                "authority": "failing_contract_test",
            }],
        },
        {"strategy": "repair"},
    )

    assert contract["allowed_targets"] == ["pkg/service.py:run"]
    assert contract["baseline_failures"][0]["failing_nodeids"] == [
        "tests/test_service.py::test_run"
    ]


def _contract() -> dict:
    return build_problem_outcome_contract(
        {
            "issue_id": "ISSUE-001",
            "rule_id": "weak_contract",
            "affected_targets": ["src/module.py:parse"],
            "evidence": ["failing_contract_test:src/module.py:parse"],
            "failure_evidence": [{
                "failure_signature": "abc", "target": "src/module.py:parse",
                "failing_nodeids": ["tests/test_module.py::test_parse"],
                "detail": "assertion failed", "authority": "failing_contract_test",
            }],
            "repair_design": {"status": "proposal_review_required", "mechanism": "tighten parser"},
        },
        {"strategy": "contract_characterization"},
    )
