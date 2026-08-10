from __future__ import annotations

from typing import Any
from runtime.role_skill_common import now_iso

def build_technical_spec(
    *,
    architecture_decision: dict[str, Any],
    role_id: str = "spec_writer",
    next_role_id: str = "implementer",
) -> dict[str, Any]:
    brief = dict(architecture_decision.get("spec_writer_brief", {}))
    chosen = dict(architecture_decision.get("chosen_option", {}))
    traceability = list(architecture_decision.get("traceability", []))
    source_context = dict(architecture_decision.get("source_context", {}))
    evidence = _source_evidence(brief, source_context)
    work_plan_contract = _work_plan_contract(brief, architecture_decision)
    acceptance = _acceptance_criteria(brief, traceability)
    preferred_targets = [] if work_plan_contract.get("source") == "TechnicalSpec.fallback_from_spec_writer_brief" else list(work_plan_contract.get("targets", []))
    extraction_contract = _extraction_contract(evidence, preferred_targets=preferred_targets)
    if work_plan_contract.get("status") == "blocked_no_first_slice" and extraction_contract.get("candidate"):
        work_plan_contract = _fallback_work_plan_contract([str(extraction_contract["candidate"])])
    acceptance = _ensure_candidate_acceptance(acceptance, extraction_contract)
    interface_contracts = _interface_contracts(brief, evidence, extraction_contract)
    implementation_handoff = {
        "recommended_role": next_role_id,
        "expected_output": "ImplementationPlan",
        "patch_scope": _handoff_patch_scope(
            brief,
            work_plan_contract,
            extraction_contract=extraction_contract,
        ),
    }
    quality_gate = _engineering_quality_gate(
        extraction_contract=extraction_contract,
        evidence=evidence,
        acceptance=acceptance,
        implementation_handoff=implementation_handoff,
    )
    return {
        "artifact_type": "TechnicalSpec",
        "role": role_id,
        "status": "ok",
        "created_at": now_iso(),
        "source_artifact": {
            "type": architecture_decision.get("artifact_type"),
            "role": architecture_decision.get("role"),
            "goal": architecture_decision.get("goal"),
        },
        "scope": brief.get("scope", []),
        "chosen_architecture_option": chosen.get("id"),
        "requirements": _requirements_from_brief(brief, traceability),
        "source_evidence": evidence,
        "extraction_contract": extraction_contract,
        "work_plan_contract": work_plan_contract,
        "interface_contracts": interface_contracts,
        "data_lifecycle": _data_lifecycle(brief, architecture_decision),
        "state_and_replay_policy": _state_and_replay_policy(brief, architecture_decision),
        "error_model": _error_model(brief, architecture_decision, extraction_contract),
        "acceptance_criteria": acceptance,
        "engineering_quality_gate": quality_gate,
        "verification_strategy": _verification_strategy(acceptance, extraction_contract, work_plan_contract),
        "constraints": brief.get("constraints", []),
        "non_goals": architecture_decision.get("non_goals", []),
        "open_questions": architecture_decision.get("open_questions", []),
        "human_review": _human_review_material(architecture_decision, extraction_contract, quality_gate),
        "traceability_table": _spec_traceability(traceability, acceptance),
        "implementation_handoff": implementation_handoff,
        "forbidden_actions_observed": [],
        "forbidden_actions_enforced": ["write_code", "edit_registry", "execute_pipeline", "promote_candidate"],
    }

def _requirements_from_brief(brief: dict[str, Any], traceability: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for index, scope_item in enumerate(brief.get("scope", []) or []):
        rows.append(
            {
                "id": f"REQ-{index + 1:03d}",
                "statement": str(scope_item),
                "source": "spec_writer_brief.scope",
                "priority": "MUST" if index == 0 else "SHOULD",
            }
        )
    offset = len(rows)
    for index, row in enumerate(traceability[:6]):
        source = row.get("source")
        rows.append(
            {
                "id": f"REQ-{offset + index + 1:03d}",
                "statement": _requirement_statement(str(row.get("requirement")), source),
                "source": source,
                "target": row.get("target"),
                "priority": "MUST",
            }
        )
    first_slice = dict(brief.get("first_slice") or {})
    for index, step in enumerate(list(first_slice.get("steps", []))[:8], start=1):
        rows.append(
            {
                "id": f"REQ-{len(rows) + 1:03d}",
                "statement": f"First-slice step {index} must be represented as a bounded implementation obligation: {step}",
                "source": first_slice.get("source") or "ProjectArchitectureSynthesis.recommended_first_slice",
                "target": _step_target(first_slice, index),
                "priority": "MUST",
            }
        )
    return rows

def _acceptance_criteria(brief: dict[str, Any], traceability: list[dict[str, Any]]) -> list[dict[str, Any]]:
    targets = _acceptance_targets(brief, traceability)
    criteria = []
    for index, target in enumerate(targets[:40]):
        criteria.append(
            {
                "id": f"AC-{index + 1:03d}",
                "criterion": target["criterion"],
                "verification": "pytest or explicit review checklist",
                "source": target.get("source"),
            }
        )
    first_slice = dict(brief.get("first_slice") or {})
    for index, step in enumerate(list(first_slice.get("steps", []))[:8], start=1):
        criteria.append(
            {
                "id": f"AC-{len(criteria) + 1:03d}",
                "criterion": f"First-slice `{first_slice.get('name')}` step {index} is implemented or explicitly blocked with evidence: {step}",
                "verification": "contract test, negative test, or explicit implementation checklist tied to the target source",
                "source": _step_target(first_slice, index) or first_slice.get("source"),
            }
        )
    criteria.append(
        {
            "id": f"AC-{len(criteria) + 1:03d}",
            "criterion": "Implementation does not mutate Capability Registry outside explicit Foundry promote.",
            "verification": "acceptance artifact and registry diff check",
        }
    )
    return criteria

def _ensure_candidate_acceptance(criteria: list[dict[str, Any]], extraction_contract: dict[str, Any]) -> list[dict[str, Any]]:
    candidate = str(extraction_contract.get("candidate") or "")
    if not candidate:
        return _renumber_acceptance(criteria)
    rows = list(criteria)
    if not any(_candidate_acceptance_is_explicit(row, candidate) for row in criteria if isinstance(row, dict)):
        rows.insert(
            0,
            {
                "id": "AC-001",
                "criterion": f"`{candidate}` satisfies the selected extraction_contract input/output shape and failure policy.",
                "verification": "contract test or explicit review checklist tied to the selected source target",
                "source": candidate,
            },
        )
    if not _has_candidate_negative_acceptance(rows, candidate):
        rows.insert(
            1,
            {
                "id": "AC-002",
                "criterion": f"`{candidate}` rejects invalid or incomplete input without hidden side effects.",
                "verification": "negative contract test or explicit failure-path review tied to the selected source target",
                "source": candidate,
            },
        )
    return _renumber_acceptance(rows)

def _candidate_acceptance_is_explicit(row: dict[str, Any], candidate: str) -> bool:
    if str(row.get("source") or "") != candidate:
        return False
    criterion = str(row.get("criterion") or "").lower()
    return "selected extraction_contract" in criterion or "input/output shape" in criterion

def _has_candidate_negative_acceptance(rows: list[dict[str, Any]], candidate: str) -> bool:
    for row in rows:
        if not isinstance(row, dict) or str(row.get("source") or "") != candidate:
            continue
        text = f"{row.get('criterion', '')} {row.get('verification', '')}".lower()
        if any(marker in text for marker in ("negative", "invalid", "failure", "fail", "reject")):
            return True
    return False

def _engineering_quality_gate(
    *,
    extraction_contract: dict[str, Any],
    evidence: list[dict[str, Any]],
    acceptance: list[dict[str, Any]],
    implementation_handoff: dict[str, Any],
) -> dict[str, Any]:
    if extraction_contract.get("status") == "blocked_no_safe_candidate":
        return {
            "artifact_type": "EngineeringQualityGate",
            "status": "blocked",
            "checks": {},
            "blocked_by": list(extraction_contract.get("blocked_by", []) or ["no_safe_source_specific_candidate"]),
            "principle": "do not hand off to Implementer without source-backed candidate and I/O contract",
        }
    checks = {
        "source_evidence_bound": bool(evidence and extraction_contract.get("evidence_source")),
        "io_contract_bound": bool(extraction_contract.get("input_contract") and extraction_contract.get("output_contract")),
        "negative_acceptance_present": _has_negative_acceptance(acceptance),
        "handoff_scope_bound": bool(implementation_handoff.get("patch_scope")),
    }
    return {
        "artifact_type": "EngineeringQualityGate",
        "status": "ready" if all(checks.values()) else "blocked",
        "checks": checks,
        "blocked_by": [key for key, ok in checks.items() if not ok],
        "principle": "Implementer receives only source-backed, contract-bound, negatively testable work.",
    }

def _has_negative_acceptance(acceptance: list[dict[str, Any]]) -> bool:
    text = " ".join(str(row.get("criterion", "")) + " " + str(row.get("verification", "")) for row in acceptance if isinstance(row, dict)).lower()
    return any(marker in text for marker in ("negative", "invalid", "failure", "fail", "ошиб", "некоррект"))

def _renumber_acceptance(criteria: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for index, row in enumerate(criteria, start=1):
        item = dict(row)
        item["id"] = f"AC-{index:03d}"
        rows.append(item)
    return rows

def _work_plan_contract(brief: dict[str, Any], architecture_decision: dict[str, Any]) -> dict[str, Any]:
    first_slice = dict(brief.get("first_slice") or architecture_decision.get("first_slice_contract") or {})
    if not first_slice:
        fallback_targets = [
            _normalize_source_ref(str(item))
            for item in list(brief.get("files_or_symbols", []))
            if _implementation_source(str(item))
        ]
        if fallback_targets:
            return _fallback_work_plan_contract(fallback_targets)
        return {
            "status": "blocked_no_first_slice",
            "source": "ArchitectureDecisionRecord.first_slice_contract",
            "name": None,
            "goal": "No source-backed first slice was provided by Architect.",
            "targets": [],
            "obligations": [],
            "blocked_by": ["missing_first_slice_contract"],
        }
    obligations = []
    steps = list(first_slice.get("steps", []))
    targets = [_normalize_source_ref(str(item)) for item in list(first_slice.get("targets", [])) if item]
    if not targets:
        return {
            "status": "blocked_no_first_slice",
            "source": first_slice.get("source") or "ArchitectureDecisionRecord.first_slice_contract",
            "name": first_slice.get("name"),
            "goal": "Architect did not provide a safe source-backed target for this first slice.",
            "targets": [],
            "knowledge_rule": first_slice.get("knowledge_rule"),
            "obligations": [],
            "blocked_by": ["no_safe_source_specific_candidate"],
        }
    for index, step in enumerate(steps[:12], start=1):
        obligations.append(
            {
                "id": f"WPC-{index:03d}",
                "step": str(step),
                "target": _step_target(first_slice, index),
                "input": "source-backed evidence, current behavior, and declared capability boundary",
                "output": "bounded implementation obligation with acceptance and rollback evidence",
                "verification": "must be linked to at least one acceptance criterion before Implementer handoff",
            }
        )
    return {
        "status": "ready" if obligations else "needs_manual_step_definition",
        "source": first_slice.get("source") or "ArchitectureDecisionRecord.first_slice_contract",
        "name": first_slice.get("name"),
        "goal": first_slice.get("goal"),
        "targets": targets[:8],
        "knowledge_rule": first_slice.get("knowledge_rule"),
        "obligations": obligations,
    }
