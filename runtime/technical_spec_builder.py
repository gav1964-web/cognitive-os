"""Generic TechnicalSpec artifact builder."""

from __future__ import annotations

from typing import Any

from .role_spec_writer_ranking import (
    candidate_level_bonus as _candidate_level_bonus,
    name_and_contract_score as _name_and_contract_score,
    operational_boundary_score as _operational_boundary_score,
)
from .role_skill_common import now_iso


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
    acceptance = _acceptance_criteria(brief, traceability)
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
        "extraction_contract": _extraction_contract(evidence),
        "acceptance_criteria": acceptance,
        "constraints": brief.get("constraints", []),
        "non_goals": architecture_decision.get("non_goals", []),
        "traceability_table": _spec_traceability(traceability, acceptance),
        "implementation_handoff": {
            "recommended_role": next_role_id,
            "expected_output": "ImplementationPlan",
            "patch_scope": brief.get("files_or_symbols", []),
        },
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
    return rows


def _acceptance_criteria(brief: dict[str, Any], traceability: list[dict[str, Any]]) -> list[dict[str, Any]]:
    targets = _acceptance_targets(brief, traceability)
    criteria = []
    for index, target in enumerate(targets[:8]):
        criteria.append(
            {
                "id": f"AC-{index + 1:03d}",
                "criterion": target["criterion"],
                "verification": "pytest or explicit review checklist",
                "source": target.get("source"),
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


def _source_evidence(brief: dict[str, Any], source_context: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for source in brief.get("files_or_symbols", []) or []:
        context = dict(source_context.get(str(source), {}))
        snippet = dict(context.get("snippet", {}))
        signature = dict(context.get("signature", {}))
        rows.append(
            {
                "source": str(source),
                "kind": context.get("kind") or "unknown",
                "snippet": snippet.get("text"),
                "signature": signature,
                "callers": context.get("callers", []),
                "callees": context.get("callees", []),
                "side_effects": context.get("side_effects", []),
                "claims": context.get("claims", []),
            }
        )
    return rows


def _extraction_contract(evidence: list[dict[str, Any]]) -> dict[str, Any]:
    ranked = _rank_extraction_candidates(evidence)
    if not ranked:
        return {
            "status": "blocked_no_safe_candidate",
            "candidate": None,
            "candidate_score": 0,
            "selection_reason": "no source-specific evidence available for a bounded extraction contract",
            "ranked_candidates": [],
            "input_contract": {},
            "output_contract": {},
            "side_effects": {"declared": [], "requires_process_boundary": False},
            "evidence_source": None,
            "blocked_by": ["no_safe_source_specific_candidate"],
        }
    candidate = dict(ranked[0].get("evidence", {})) if ranked else {}
    args = list(dict(candidate.get("signature", {})).get("args", []))
    input_contract = {str(arg.get("name") or "payload"): str(arg.get("annotation") or "Any") for arg in args}
    return {
        "candidate": candidate.get("source"),
        "candidate_score": ranked[0]["score"] if ranked else 0,
        "selection_reason": "; ".join(ranked[0]["reasons"]) if ranked else "no source evidence available",
        "ranked_candidates": [
            {
                "source": item.get("source"),
                "kind": item.get("kind"),
                "score": item.get("score"),
                "reasons": item.get("reasons", []),
                "side_effects": item.get("side_effects", []),
            }
            for item in ranked[:6]
        ],
        "input_contract": input_contract or {"payload": "Any"},
        "output_contract": {"result": str(dict(candidate.get("signature", {})).get("returns") or "Any")},
        "side_effects": {
            "declared": candidate.get("side_effects", []),
            "requires_process_boundary": bool(candidate.get("side_effects")),
        },
        "evidence_source": candidate.get("source"),
    }


def _rank_extraction_candidates(evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ranked = []
    for index, row in enumerate(evidence):
        candidate = dict(row)
        score = 0
        reasons = []
        kind = str(candidate.get("kind") or "")
        side_effects = list(candidate.get("side_effects", []) or [])
        signature = dict(candidate.get("signature", {}) or {})
        claims = [str(item) for item in candidate.get("claims", []) or []]

        if kind == "pure_transform":
            score += 40
            reasons.append("pure transform candidate")
        elif kind == "central_flow_node":
            score += 45
            reasons.append("central flow node with subsystem-level evidence")
        elif kind == "broad_function":
            score += 38
            reasons.append("broad function can anchor a meaningful first slice")
        else:
            score += 5
            reasons.append("available source evidence")

        if candidate.get("central_flow_node"):
            score += 20
            reasons.append("central flow evidence available")
        if candidate.get("mixed_responsibilities"):
            score += 12
            reasons.append("mixed-responsibility evidence available")
        if candidate.get("process_boundary_reasons"):
            score += 8
            reasons.append("process-boundary evidence available")
        if candidate.get("candidate_level"):
            score += _candidate_level_bonus(str(candidate.get("candidate_level")))
            reasons.append(f"ProjectMapReport ranked as {candidate.get('candidate_level')}")
        if candidate.get("candidate_score") is not None:
            score += min(int(candidate.get("candidate_score") or 0), 100) // 20
            reasons.append("ProjectMapReport candidate score available")

        if not side_effects:
            score += 25
            reasons.append("no declared side effects")
        else:
            score -= 20
            reasons.append("declared side effects require tighter isolation")

        if signature.get("args"):
            score += 10
            reasons.append("input contract can be inferred from signature")
        if signature.get("returns"):
            score += 10
            reasons.append("output contract can be inferred from signature")
        if candidate.get("snippet"):
            score += 5
            reasons.append("snippet available for source-backed review")
        if candidate.get("callers"):
            score += 5
            reasons.append("caller context available")
        name_score, name_reasons = _name_and_contract_score(str(candidate.get("source") or ""), signature, side_effects)
        score += name_score
        reasons.extend(name_reasons)
        if any("idempotency" in claim.lower() for claim in claims):
            score -= 10
            reasons.append("idempotency risk claim present")
        if any("side effect" in claim.lower() for claim in claims):
            score -= 10
            reasons.append("side-effect risk claim present")
        policy_score, policy_reasons = _operational_boundary_score(str(candidate.get("source") or ""), signature, claims)
        score += policy_score
        reasons.extend(policy_reasons)

        ranked.append(
            {
                "source": candidate.get("source"),
                "kind": candidate.get("kind"),
                "score": score,
                "reasons": reasons,
                "side_effects": side_effects,
                "evidence": candidate,
                "index": index,
            }
        )
    return sorted(ranked, key=lambda item: (-int(item["score"]), int(item["index"]), str(item.get("source") or "")))


def _requirement_statement(requirement: str, source: object) -> str:
    source_text = str(source or "").strip()
    if requirement == "Capability candidate requires TechnicalSpec." and source_text:
        return f"{source_text} must have explicit input/output contract, side-effect policy, and Foundry quality gate."
    if requirement == "Risk must be addressed or accepted before promotion." and source_text:
        return f"Risk from {source_text} must be mitigated or explicitly accepted before promotion."
    return requirement


def _acceptance_targets(brief: dict[str, Any], traceability: list[dict[str, Any]]) -> list[dict[str, str]]:
    rows = []
    for row in traceability[:8]:
        source = row.get("source")
        requirement = str(row.get("acceptance") or row.get("requirement") or "")
        rows.append({"source": str(source or ""), "criterion": _acceptance_statement(requirement, source)})
    if rows:
        return rows
    return [
        {"source": "spec_writer_brief", "criterion": str(item)}
        for item in brief.get("acceptance_targets", [])
        if item
    ]


def _acceptance_statement(requirement: str, source: object) -> str:
    source_text = str(source or "").strip()
    if requirement == "Capability candidate requires TechnicalSpec." and source_text:
        return f"{source_text} has a bounded TechnicalSpec with source evidence, input contract, output contract, and negative-test expectation."
    if requirement == "Risk must be addressed or accepted before promotion." and source_text:
        return f"{source_text} risk is represented in constraints, acceptance criteria, or non-goals before any implementation handoff."
    return requirement or f"{source_text} is covered by the TechnicalSpec."


def _spec_traceability(
    traceability: list[dict[str, Any]],
    acceptance: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows = []
    for index, row in enumerate(traceability[: len(acceptance)]):
        rows.append(
            {
                "source": row.get("source"),
                "requirement": row.get("requirement"),
                "acceptance_id": acceptance[index]["id"],
            }
        )
    return rows

