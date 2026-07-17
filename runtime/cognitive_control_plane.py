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


def run_prompt_product_control_plane(
    *,
    prompt: str,
    prompt_adequacy: dict[str, Any],
    supported_template: str | None,
    llm_invoked: bool = False,
) -> dict[str, Any]:
    gate = _prompt_product_gate(prompt_adequacy, supported_template)
    transition = _prompt_product_transition(prompt_adequacy, gate)
    escalation = _prompt_product_escalation(prompt, prompt_adequacy, gate, llm_invoked)
    return {
        "artifact_type": "CognitiveControlPlaneDecision",
        "layer": "L4.0",
        "mode": "prompt_to_product",
        "status": "ok",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "goal": prompt,
        "prompt_adequacy": prompt_adequacy,
        "artifact_promotion_gate": {"status": "not_applicable", "reason": "prompt_to_product_uses_prompt_product_gate"},
        "prompt_product_gate": gate,
        "role_transition": transition,
        "semantic_escalation": escalation,
        "crystallization_backlog": _prompt_product_crystallization_backlog(transition, gate, escalation),
        "principle": "Prompt-to-product advances only through explicit gates; L4.5 is a bounded hypothesis source, not a free executor",
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


def _prompt_product_gate(prompt_adequacy: dict[str, Any], supported_template: str | None) -> dict[str, Any]:
    status = prompt_adequacy.get("status")
    checks = [
        {
            "code": "prompt_adequacy_ready",
            "passed": status == "ready",
            "actual": status,
        },
        {
            "code": "supported_package_template_available",
            "passed": bool(supported_template),
            "actual": supported_template,
        },
    ]
    passed = all(item["passed"] for item in checks)
    return {
        "status": "passed" if passed else "blocked",
        "checks": checks,
        "supported_template": supported_template,
        "can_build_package": passed,
    }


def _prompt_product_transition(prompt_adequacy: dict[str, Any], gate: dict[str, Any]) -> dict[str, Any]:
    prompt_status = prompt_adequacy.get("status")
    if gate.get("can_build_package"):
        next_action = "build_verified_system_package"
        reason = "prompt_ready_and_template_supported"
    elif prompt_status in {"needs_clarification", "too_broad"}:
        next_action = "ask_clarification"
        reason = f"prompt_{prompt_status}"
    elif prompt_status == "unsupported":
        next_action = "stop_unsupported"
        reason = "prompt_unsupported_by_policy"
    else:
        next_action = "stop_unsupported"
        reason = "no_supported_package_template"
    return {
        "status": "decided",
        "next_action": next_action,
        "reason_code": reason,
        "controller": "deterministic_prompt_product_transition_v0.1",
    }


def _prompt_product_escalation(
    prompt: str,
    prompt_adequacy: dict[str, Any],
    gate: dict[str, Any],
    llm_invoked: bool,
) -> dict[str, Any]:
    reasons: list[str] = []
    if prompt_adequacy.get("status") == "ready" and not gate.get("can_build_package"):
        reasons.append("no_supported_package_template")
    if _is_bounded_intake_uncertainty(prompt, prompt_adequacy):
        reasons.append("prompt_intake_uncertainty")
    if prompt_adequacy.get("status") == "unsupported" and prompt_adequacy.get("system_type") is None:
        reasons.append("unsupported_system_type_requires_semantic_classification")
    return {
        "l4_5_required": bool(reasons),
        "reasons": reasons,
        "llm_already_invoked": llm_invoked,
        "policy": "invoke L4.5 only when deterministic prompt gates cannot classify or route an otherwise bounded request",
    }


def _is_bounded_intake_uncertainty(prompt: str, prompt_adequacy: dict[str, Any]) -> bool:
    if prompt_adequacy.get("status") != "needs_clarification":
        return False
    lower = prompt.lower()
    goal_spec = dict(prompt_adequacy.get("goal_spec", {}))
    boundary = dict(prompt_adequacy.get("boundary_classification", {}))
    if boundary.get("risk_markers") or boundary.get("unsupported_markers"):
        return False
    if any(marker in lower for marker in ("полезную штуку", "что-нибудь", "anything", "do something")):
        return False
    has_product_shape = any(marker in lower for marker in ("cli", ".py", "утилит", "script", "fastapi", "service", "служб"))
    has_domain_signal = any(
        marker in lower
        for marker in (
            "картин",
            "изображ",
            "фото",
            "image",
            "picture",
            "csv",
            "json",
            "xlsx",
            "markdown",
            "pdf",
            "html",
            "url",
            "текст",
            "файл",
        )
    )
    return (
        goal_spec.get("intent") == "implementation"
        and prompt_adequacy.get("system_type") in {"cli", "file_processing_utility", "fastapi_service", "small_local_service"}
        and boundary.get("boundary") in {"incomplete_bounded_prompt", "bounded_supported_class"}
        and has_product_shape
        and has_domain_signal
    )


def _prompt_product_crystallization_backlog(
    transition: dict[str, Any],
    gate: dict[str, Any],
    escalation: dict[str, Any],
) -> list[dict[str, Any]]:
    if escalation.get("l4_5_required"):
        return []
    if gate.get("status") != "passed":
        return []
    return [
        {
            "candidate": "prompt_product_transition_rule",
            "pattern": transition.get("reason_code"),
            "target": "runtime/cognitive_control_plane.py",
            "action": "keep prompt-to-product routing deterministic and covered by tests",
        },
        {
            "candidate": "supported_package_template",
            "pattern": gate.get("supported_template"),
            "target": "curricula/programmer_prompt_stage2",
            "action": "promote stable generated-package case coverage into the curriculum catalog",
        },
    ]


def _blocked_no_safe_candidate(artifacts: dict[str, dict[str, Any]]) -> bool:
    for artifact in artifacts.values():
        if _has_blocked_candidate_signal(artifact):
            return True
    return False


def _has_blocked_candidate_signal(value: Any) -> bool:
    if isinstance(value, dict):
        status = value.get("status")
        reason = value.get("reason")
        code = value.get("code")
        if status == "blocked_no_safe_candidate" or reason == "no_safe_source_specific_candidate" or code == "no_safe_source_specific_candidate":
            return True
        return any(_has_blocked_candidate_signal(item) for item in value.values())
    if isinstance(value, list):
        return any(_has_blocked_candidate_signal(item) for item in value if isinstance(item, (dict, list)))
    return value in {"blocked_no_safe_candidate", "no_safe_source_specific_candidate"}


def _has_architect_fallback(artifacts: dict[str, dict[str, Any]]) -> bool:
    adr = dict(artifacts.get("architecture_decision", {}))
    advisory = dict(adr.get("architect_advisory", {}))
    return advisory.get("source") == "deterministic_fallback"
