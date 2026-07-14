"""Deterministic L4.0 cognitive control plane.

The control plane owns repeatable orchestration decisions. It does not replace
L4 semantic reasoning; it decides when semantic reasoning is actually needed.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def run_cognitive_control_plane(
    *,
    goal: str,
    artifacts: dict[str, dict[str, Any]],
    review: dict[str, Any],
    prompt_adequacy: dict[str, Any] | None = None,
    llm_invoked: bool = False,
) -> dict[str, Any]:
    promotion = _artifact_promotion_gate(artifacts, review)
    transition = _role_transition(review, promotion)
    escalation = _semantic_escalation_policy(
        goal=goal,
        artifacts=artifacts,
        review=review,
        promotion=promotion,
        prompt_adequacy=prompt_adequacy,
        llm_invoked=llm_invoked,
    )
    return {
        "artifact_type": "CognitiveControlPlaneDecision",
        "layer": "L4.0",
        "status": "ok",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "goal": goal,
        "prompt_adequacy": prompt_adequacy or {"status": "not_evaluated", "reason": "role_pipeline_goal"},
        "artifact_promotion_gate": promotion,
        "role_transition": transition,
        "semantic_escalation": escalation,
        "crystallization_backlog": _crystallization_backlog(transition, promotion, escalation),
        "principle": "code controls known repeatable decisions; L4.5 is reserved for semantic uncertainty",
    }


def _artifact_promotion_gate(artifacts: dict[str, dict[str, Any]], review: dict[str, Any]) -> dict[str, Any]:
    required = {
        "architecture_decision": "ArchitectureDecisionRecord",
        "technical_spec": "TechnicalSpec",
        "implementation_plan": "ImplementationPlan",
        "test_plan": "TestPlan",
        "review_findings": "ReviewFindings",
    }
    checks: list[dict[str, Any]] = []
    for key, artifact_type in required.items():
        artifact = dict(artifacts.get(key, {}))
        checks.append(
            {
                "code": f"{key}_present",
                "passed": artifact.get("artifact_type") == artifact_type,
                "expected": artifact_type,
                "actual": artifact.get("artifact_type"),
            }
        )
    checks.append(
        {
            "code": "review_conformance_passed",
            "passed": review.get("conformance_status") in {None, "passed"},
            "actual": review.get("conformance_status"),
        }
    )
    checks.append(
        {
            "code": "review_recommendation_valid",
            "passed": review.get("recommendation") in {"approve", "approve_with_risks", "request_rework"},
            "actual": review.get("recommendation"),
        }
    )
    passed = all(item["passed"] for item in checks)
    return {
        "status": "passed" if passed else "blocked",
        "checks": checks,
        "can_promote_to_next_role": passed and review.get("recommendation") != "request_rework",
    }


def _role_transition(review: dict[str, Any], promotion: dict[str, Any]) -> dict[str, Any]:
    recommendation = review.get("recommendation")
    if promotion.get("status") != "passed":
        next_action = "rework_role_artifacts"
        reason = "artifact_promotion_gate_failed"
    elif recommendation == "request_rework":
        next_action = "rework_role_artifacts"
        reason = "review_requested_rework"
    elif recommendation == "approve_with_risks":
        next_action = "review_risks_then_run_project_transform"
        reason = "approved_with_material_risks"
    else:
        next_action = "run_project_transform"
        reason = "review_approved"
    return {
        "status": "decided",
        "next_action": next_action,
        "reason_code": reason,
        "controller": "deterministic_role_transition_v0.1",
    }


def _semantic_escalation_policy(
    *,
    goal: str,
    artifacts: dict[str, dict[str, Any]],
    review: dict[str, Any],
    promotion: dict[str, Any],
    prompt_adequacy: dict[str, Any] | None,
    llm_invoked: bool,
) -> dict[str, Any]:
    reasons: list[str] = []
    prompt_status = (prompt_adequacy or {}).get("status")
    if prompt_status in {"needs_clarification", "unsupported", "too_broad"}:
        reasons.append(f"prompt_{prompt_status}")
    if promotion.get("status") == "blocked" and review.get("conformance_status") == "passed":
        reasons.append("promotion_blocked_without_contract_failure")
    if _blocked_no_safe_candidate(artifacts):
        reasons.append("no_safe_source_specific_candidate")
    if _has_architect_fallback(artifacts):
        reasons.append("architect_advisory_backend_failed")
    if review.get("recommendation") == "request_rework" and review.get("conformance_status") == "passed":
        reasons.append("semantic_rework_after_contracts_passed")
    return {
        "l4_5_required": bool(reasons),
        "reasons": reasons,
        "llm_already_invoked": llm_invoked,
        "policy": "invoke L4.5 only for ambiguity, semantic conflict, unknown candidate, or failed advisory backend",
    }


def _crystallization_backlog(
    transition: dict[str, Any],
    promotion: dict[str, Any],
    escalation: dict[str, Any],
) -> list[dict[str, Any]]:
    if escalation.get("l4_5_required"):
        return []
    backlog = [
        {
            "candidate": "role_transition_rule",
            "pattern": transition.get("reason_code"),
            "target": "runtime/cognitive_control_plane.py",
            "action": "keep deterministic transition covered by tests",
        }
    ]
    if promotion.get("status") == "passed":
        backlog.append(
            {
                "candidate": "artifact_promotion_gate",
                "pattern": "all_role_artifacts_present_and_review_conformant",
                "target": "ContractRegistry + role pipeline tests",
                "action": "promote repeated artifact checks into contract catalog where stable",
            }
        )
    return backlog


def _blocked_no_safe_candidate(artifacts: dict[str, dict[str, Any]]) -> bool:
    for artifact in artifacts.values():
        text = str(artifact)
        if "blocked_no_safe_candidate" in text or "no_safe_source_specific_candidate" in text:
            return True
    return False


def _has_architect_fallback(artifacts: dict[str, dict[str, Any]]) -> bool:
    adr = dict(artifacts.get("architecture_decision", {}))
    advisory = dict(adr.get("architect_advisory", {}))
    return advisory.get("source") == "deterministic_fallback"
