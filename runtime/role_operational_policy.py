"""Validation and summaries for role_directory operational policy."""

from __future__ import annotations

from typing import Any

from .role_directory import load_role_directory


def role_operational_policy_report(directory: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = directory or load_role_directory()
    roles = dict(payload.get("roles") or {})
    cases = []
    for role_id, role in roles.items():
        cases.append(_role_case(str(role_id), dict(role)))
    failed = [case for case in cases if case["status"] != "ok"]
    return {
        "artifact_type": "RoleOperationalPolicyReport",
        "schema_version": payload.get("schema_version"),
        "status": "ok" if not failed else "failed",
        "role_count": len(cases),
        "summary": {
            "ok": len(cases) - len(failed),
            "failed": len(failed),
            "llm_allowed": sum(1 for case in cases if case["llm_allowed"]),
            "kb_candidates_enabled": sum(1 for case in cases if case["kb_write_candidate"]),
            "auto_promote_forbidden": all(case["auto_promote_forbidden"] for case in cases),
        },
        "cases": cases,
    }


def _role_case(role_id: str, role: dict[str, Any]) -> dict[str, Any]:
    contract = dict(role.get("contract") or {})
    fallback = dict(role.get("fallback_policy") or {})
    llm_policy = dict(role.get("llm_policy") or {})
    kb_policy = dict(role.get("kb_policy") or {})
    checks = {
        "contract_inputs_present": bool(contract.get("inputs")),
        "contract_outputs_present": bool(contract.get("outputs")),
        "gates_present": bool(role.get("gates")),
        "fallback_policy_present": bool(fallback),
        "llm_policy_present": bool(llm_policy),
        "kb_policy_present": bool(kb_policy),
        "stop_conditions_present": bool(role.get("stop_conditions")),
        "quality_criteria_present": bool(role.get("quality_criteria")),
        "kb_auto_promote_forbidden": kb_policy.get("auto_promote") is False,
    }
    warnings = [name for name, ok in checks.items() if not ok]
    return {
        "role_id": role_id,
        "status": "ok" if not warnings else "failed",
        "checks": checks,
        "warnings": warnings,
        "llm_allowed": bool(llm_policy.get("allowed")),
        "kb_write_candidate": bool(kb_policy.get("write_candidate")),
        "auto_promote_forbidden": kb_policy.get("auto_promote") is False,
        "fallback_actions": dict(fallback),
    }
