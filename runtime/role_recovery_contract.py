"""Interpret bounded return paths between roles without authorizing a retry."""

from __future__ import annotations

from typing import Any

from .interpreter_authority import load_interpreter_authority_policy


RETURN_OUTCOMES = {"needs_rework", "research_more"}


def build_role_recovery_contract(
    *,
    producer: str,
    return_to: str,
    outcome: str,
    reason_code: str,
    target: str,
    scope: list[str],
    original_target: str,
    original_scope: list[str],
    previous_returns: int = 0,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rules = policy or load_interpreter_authority_policy()
    recovery = dict(rules["recovery"])
    checks = {
        "return_outcome_allowed": outcome in RETURN_OUTCOMES,
        "producer_present": bool(producer),
        "consumer_present": bool(return_to),
        "reason_code_present": bool(reason_code),
        "target_preserved": target == original_target,
        "scope_not_expanded": set(scope).issubset(set(original_scope)),
        "return_budget_available": previous_returns < int(recovery["maximum_returns"]),
    }
    failed = [name for name, passed in checks.items() if not passed]
    return {
        "artifact_type": "RoleRecoveryContract",
        "schema_version": "role_recovery_contract.v1",
        "status": "return_ready" if not failed else "controlled_stop",
        "producer": producer,
        "return_to": return_to,
        "outcome": outcome,
        "reason_code": reason_code,
        "target": target,
        "scope": sorted(set(scope)),
        "return_number": previous_returns + 1,
        "checks": checks,
        "failed_checks": failed,
        "execution_authorized": False,
        "automatic_retry": False,
        "scope_expansion_allowed": False,
    }
