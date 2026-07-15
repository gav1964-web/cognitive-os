"""L4.0 validation gate for L4.5 semantic hypotheses."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .semantic_reasoner import validate_semantic_hypothesis_proposal


def validate_l45_semantic_proposal(
    *,
    request: dict[str, Any],
    proposal: dict[str, Any],
) -> dict[str, Any]:
    """Turn an L4.5 proposal into an explicit L4.0 gate decision."""

    contract_validation = validate_semantic_hypothesis_proposal(request=request, proposal=proposal)
    checks = _quality_checks(request, proposal, contract_validation)
    score = sum(1 for item in checks if item["passed"]) / len(checks)
    failed_codes = [item["code"] for item in checks if not item["passed"]]
    accepted_action = _accepted_action(str(proposal.get("hypothesis_type") or ""))
    status = "accepted" if not failed_codes and accepted_action != "blocked" else "blocked"
    if status == "blocked":
        accepted_action = "blocked"
    return {
        "artifact_type": "L4SemanticValidationResult",
        "layer": "L4.0",
        "status": status,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_request": {
            "artifact_type": request.get("artifact_type"),
            "layer": request.get("layer"),
            "trigger_reasons": list(request.get("trigger_reasons", [])),
            "return_path": dict(request.get("return_path", {})),
        },
        "source_proposal": {
            "artifact_type": proposal.get("artifact_type"),
            "layer": proposal.get("layer"),
            "status": proposal.get("status"),
            "hypothesis_type": proposal.get("hypothesis_type"),
            "confidence": proposal.get("confidence"),
        },
        "contract_validation": contract_validation,
        "quality": {
            "score": round(score, 3),
            "checks": checks,
            "failed_codes": failed_codes,
        },
        "accepted_action": accepted_action,
        "decision": {
            "next_action": accepted_action,
            "reason_code": _reason_code(status, failed_codes, str(proposal.get("hypothesis_type") or "")),
            "backlog_allowed": accepted_action == "record_template_backlog",
            "clarification_allowed": accepted_action == "ask_clarification",
        },
        "explanation": _explanation(status, accepted_action, failed_codes, proposal),
        "forbidden_actions_observed": _forbidden_actions(request, proposal),
        "human_readable_summary": _summary(status, accepted_action, failed_codes),
    }


def _quality_checks(
    request: dict[str, Any],
    proposal: dict[str, Any],
    contract_validation: dict[str, Any],
) -> list[dict[str, Any]]:
    hypothesis_type = str(proposal.get("hypothesis_type") or "")
    proposal_body = dict(proposal.get("proposal", {})) if isinstance(proposal.get("proposal"), dict) else {}
    evidence_refs = proposal.get("evidence_refs", [])
    risks = proposal.get("risks", [])
    confidence = _confidence(proposal.get("confidence"))
    allowed_empty_proposal = hypothesis_type in {"clarification_question", "unsupported_reason", "knowledge_gap"}
    return [
        {
            "code": "contract_valid",
            "passed": contract_validation.get("status") == "ok",
            "detail": ",".join(contract_validation.get("violations", [])),
        },
        {
            "code": "returns_to_l4_gate",
            "passed": proposal.get("return_to_gate") is True
            and dict(request.get("return_path", {})).get("target_layer") == "L4.0",
            "detail": "L4.5 output must return to L4.0 before action",
        },
        {
            "code": "evidence_present",
            "passed": isinstance(evidence_refs, list) and len(evidence_refs) > 0,
            "detail": "semantic hypotheses need evidence refs",
        },
        {
            "code": "risks_present",
            "passed": isinstance(risks, list) and len(risks) > 0,
            "detail": "semantic hypotheses need explicit risks",
        },
        {
            "code": "confidence_sane",
            "passed": confidence >= 0.35,
            "detail": f"confidence={confidence}",
        },
        {
            "code": "proposal_payload_present",
            "passed": bool(proposal_body) or allowed_empty_proposal,
            "detail": "proposal body may be empty only for clarification/unsupported/knowledge gap",
        },
        {
            "code": "no_forbidden_actions",
            "passed": not _forbidden_actions(request, proposal),
            "detail": "L4.5 may not request execution, mutation, promotion or gate bypass",
        },
        {
            "code": "no_runtime_mutation_claim",
            "passed": not _contains_runtime_mutation_claim(proposal_body),
            "detail": "proposal must not claim runtime state was changed",
        },
    ]


def _accepted_action(hypothesis_type: str) -> str:
    return {
        "new_template_candidate": "record_template_backlog",
        "template_mapping_candidate": "rerun_deterministic_gate",
        "clarification_question": "ask_clarification",
        "unsupported_reason": "stop_unsupported",
        "risk_interpretation": "record_semantic_note",
        "architecture_option": "record_semantic_note",
        "rework_target": "request_role_rework",
        "knowledge_gap": "record_knowledge_gap",
    }.get(hypothesis_type, "blocked")


def _reason_code(status: str, failed_codes: list[str], hypothesis_type: str) -> str:
    if status == "blocked":
        return "l45_proposal_failed_l4_validation:" + ",".join(failed_codes)
    return f"l45_{hypothesis_type}_accepted_by_l4_gate"


def _summary(status: str, accepted_action: str, failed_codes: list[str]) -> str:
    if status == "accepted":
        return f"L4.0 accepted bounded L4.5 hypothesis and routed it to {accepted_action}."
    return "L4.0 blocked L4.5 hypothesis: " + ", ".join(failed_codes)


def _explanation(
    status: str,
    accepted_action: str,
    failed_codes: list[str],
    proposal: dict[str, Any],
) -> dict[str, Any]:
    if status == "accepted":
        return {
            "verdict": "accepted",
            "why": [
                "proposal matches the requested contract",
                "proposal returns to L4.0 instead of executing directly",
                "evidence, risks and confidence are explicit",
            ],
            "next_step": accepted_action,
            "human_note": f"L4.0 accepted {proposal.get('hypothesis_type')} and routed it to {accepted_action}.",
        }
    return {
        "verdict": "blocked",
        "why": failed_codes,
        "next_step": "inspect_or_rework_l45_proposal",
        "human_note": "L4.0 blocked the L4.5 proposal because it failed one or more gate checks.",
    }


def _forbidden_actions(request: dict[str, Any], proposal: dict[str, Any]) -> list[str]:
    forbidden = set(str(item) for item in request.get("forbidden_actions", []))
    proposal_body = dict(proposal.get("proposal", {})) if isinstance(proposal.get("proposal"), dict) else {}
    actions = set(str(item) for item in proposal_body.get("actions", []) if item is not None)
    return sorted(forbidden & actions)


def _contains_runtime_mutation_claim(proposal_body: dict[str, Any]) -> bool:
    text = " ".join(str(value).lower() for value in proposal_body.values())
    markers = [
        "already built",
        "already executed",
        "registry updated",
        "template added",
        "source edited",
        "runtime mutated",
    ]
    return any(marker in text for marker in markers)


def _confidence(value: Any) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, parsed))
