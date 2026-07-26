"""Red-team checks for SpecWriter output before Implementer handoff."""

from __future__ import annotations

from typing import Any


def red_team_technical_spec(spec: dict[str, Any], architecture_decision: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return an explicit handoff verdict for a TechnicalSpec.

    The normal artifact quality score checks that fields exist. This red-team
    pass asks a harder question: can Implementer start without guessing?
    """

    architecture_decision = architecture_decision or {}
    contract = dict(spec.get("extraction_contract", {}))
    work_plan = dict(spec.get("work_plan_contract", {}))
    acceptance = list(spec.get("acceptance_criteria", []) or [])
    interface_contracts = list(spec.get("interface_contracts", []) or [])
    findings: list[dict[str, Any]] = []

    if _blocked_no_safe_candidate(contract, work_plan):
        return {
            "artifact_type": "SpecWriterRedTeamReport",
            "status": "pass",
            "handoff_verdict": "blocked_no_safe_candidate",
            "blocking_findings": [],
            "warnings": [],
            "score": 1.0,
            "checked_contract": None,
        }

    _require(findings, bool(contract.get("candidate")), "missing_candidate", "TechnicalSpec has no selected source target.")
    _require(
        findings,
        not _contract_contains_weak_any(contract),
        "weak_any_contract",
        "Input/output contract still contains unqualified Any or empty result shape.",
        severity="high",
    )
    _require(
        findings,
        bool(contract.get("contract_family")) or _plain_contract_is_specific(contract),
        "missing_contract_family_or_specific_shape",
        "Contract must either declare a domain contract_family or have specific I/O shapes.",
    )
    _require(
        findings,
        _side_effects_are_gated(contract),
        "side_effects_without_gate",
        "Side-effecting contract needs idempotency, process-boundary, validation, or retry gate.",
    )
    _require(
        findings,
        _acceptance_targets_candidate(acceptance, str(contract.get("candidate") or "")),
        "candidate_acceptance_missing",
        "At least one acceptance criterion must directly reference the selected candidate.",
    )
    _require(
        findings,
        _work_plan_targets_are_source_backed(work_plan),
        "work_plan_not_source_backed",
        "Work-plan obligations must point at source-backed targets.",
    )
    _require(
        findings,
        _interface_contract_for_candidate(interface_contracts, str(contract.get("candidate") or "")),
        "candidate_interface_contract_missing",
        "Interface contracts must include the selected candidate.",
    )
    _require(
        findings,
        _traceability_covers_first_slice(spec, architecture_decision),
        "first_slice_traceability_gap",
        "First-slice obligations must be visible in requirements or traceability.",
        severity="medium",
    )

    blocking = [row for row in findings if row["severity"] == "high"]
    warnings = [row for row in findings if row["severity"] != "high"]
    return {
        "artifact_type": "SpecWriterRedTeamReport",
        "status": "pass" if not blocking else "fail",
        "handoff_verdict": "ready_for_implementer" if not blocking else "return_to_spec_writer",
        "blocking_findings": blocking,
        "warnings": warnings,
        "score": round(max(0.0, 1.0 - len(blocking) * 0.25 - len(warnings) * 0.08), 4),
        "checked_contract": contract.get("candidate"),
    }


def _require(
    findings: list[dict[str, Any]],
    condition: bool,
    code: str,
    message: str,
    *,
    severity: str = "high",
) -> None:
    if not condition:
        findings.append({"severity": severity, "code": code, "message": message})


def _blocked_no_safe_candidate(contract: dict[str, Any], work_plan: dict[str, Any]) -> bool:
    return (
        contract.get("status") == "blocked_no_safe_candidate"
        and "no_safe_source_specific_candidate" in list(contract.get("blocked_by", []) or [])
        and work_plan.get("status") == "blocked_no_first_slice"
    )


def _contract_contains_weak_any(contract: dict[str, Any]) -> bool:
    if contract.get("contract_family"):
        return False
    shapes = [dict(contract.get("input_contract", {})), dict(contract.get("output_contract", {}))]
    for shape in shapes:
        if not shape:
            return True
        values = [str(value).strip().lower() for value in shape.values()]
        if any(value in {"", "any", "none"} for value in values):
            return True
    return False


def _plain_contract_is_specific(contract: dict[str, Any]) -> bool:
    values = list(dict(contract.get("input_contract", {})).values()) + list(dict(contract.get("output_contract", {})).values())
    return bool(values) and all(len(str(value).strip()) >= 3 and str(value).strip().lower() != "any" for value in values)


def _side_effects_are_gated(contract: dict[str, Any]) -> bool:
    side_effects = dict(contract.get("side_effects", {}))
    declared = list(side_effects.get("declared", []) or [])
    if not declared:
        return True
    return bool(
        side_effects.get("requires_validation_gate")
        or side_effects.get("requires_process_boundary")
        or side_effects.get("idempotency_required")
        or side_effects.get("retry_policy")
    )


def _acceptance_targets_candidate(acceptance: list[Any], candidate: str) -> bool:
    if not candidate:
        return False
    return any(candidate in str(row) for row in acceptance if isinstance(row, dict))


def _work_plan_targets_are_source_backed(work_plan: dict[str, Any]) -> bool:
    obligations = list(work_plan.get("obligations", []) or [])
    if not obligations:
        return False
    return all(_looks_like_source(dict(row).get("target")) for row in obligations[:4] if isinstance(row, dict))


def _interface_contract_for_candidate(rows: list[Any], candidate: str) -> bool:
    if not candidate:
        return False
    return any(isinstance(row, dict) and row.get("source") == candidate for row in rows)


def _traceability_covers_first_slice(spec: dict[str, Any], architecture_decision: dict[str, Any]) -> bool:
    first_slice = dict(architecture_decision.get("first_slice_contract", {}))
    if not first_slice:
        first_slice = dict(dict(spec.get("work_plan_contract", {})))
    name = str(first_slice.get("name") or "")
    if not name:
        return True
    haystack = " ".join(
        [
            str(spec.get("requirements", "")),
            str(spec.get("traceability_table", "")),
            str(spec.get("work_plan_contract", "")),
        ]
    )
    return name in haystack


def _looks_like_source(value: object) -> bool:
    text = str(value or "")
    return bool(text and (":" in text or "/" in text or "\\" in text or text.endswith(".py")))
