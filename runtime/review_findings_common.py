from __future__ import annotations

from typing import Any


def finding(code: str, severity: str, description: str) -> dict[str, str]:
    return {"code": code, "severity": severity, "description": description}


def check_row(
    code: str,
    passed: bool,
    description: str,
    detail: dict[str, Any] | None = None,
) -> dict[str, Any]:
    row = {"code": code, "passed": bool(passed), "description": description}
    if detail:
        row["detail"] = detail
    return row


def blocked_handoff(implementation_plan: dict[str, Any], test_plan: dict[str, Any]) -> bool:
    return (
        dict(implementation_plan.get("implementation_target", {})).get("status")
        == "blocked_no_safe_candidate"
        or test_plan.get("status") == "blocked_no_safe_candidate"
    )


def target_is_covered(test_plan: dict[str, Any], target: str) -> bool:
    if not target:
        return False
    rows = [
        *list(test_plan.get("acceptance_tests", [])),
        *list(test_plan.get("negative_tests", [])),
        *list(test_plan.get("contract_test_matrix", [])),
        *list(test_plan.get("regression_risks", [])),
    ]
    return any(isinstance(row, dict) and row.get("target") == target for row in rows)


def nonzero(value: Any) -> bool:
    try:
        return value is not None and int(value) != 0
    except (TypeError, ValueError):
        return True
