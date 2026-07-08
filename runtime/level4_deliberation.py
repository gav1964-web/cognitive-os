"""Level 4 deliberation artifact builder.

This module keeps Level 4 reasoning explicit and auditable without making it a
second executor. The output is a compact route review: available route
alternatives, what was chosen, why it looks safe enough to continue, and what
should be watched.
"""

from __future__ import annotations

from typing import Any

from .goal_orchestrator import GoalDecision
from .registry import CapabilityRegistry


def build_deliberation(
    *,
    goal: str,
    decision: GoalDecision,
    registry: CapabilityRegistry,
    memory_preflight: dict[str, Any],
    dialogue_preflight: dict[str, Any] | None = None,
) -> dict[str, Any]:
    capabilities = [_capability_row(registry, capability_id) for capability_id in decision.required_capabilities]
    risks = _risks(decision, capabilities, memory_preflight, dialogue_preflight)
    recommendation = _recommendation(decision, risks)
    alternatives = _route_alternatives(decision, capabilities, risks, memory_preflight)
    selected = _select_alternative(alternatives)
    return {
        "goal": goal,
        "action": decision.action,
        "reason_code": decision.reason_code,
        "route": _route_label(decision),
        "capabilities": capabilities,
        "memory": {
            "recommendation": memory_preflight.get("recommendation"),
            "template_recommendation": memory_preflight.get("template_recommendation"),
            "match_count": len(memory_preflight.get("matches", [])),
            "template_match_count": len(memory_preflight.get("template_matches", [])),
        },
        "dialogue": {
            "enabled": dialogue_preflight is not None,
            "match_count": len((dialogue_preflight or {}).get("recall", {}).get("matches", [])),
            "active_topic": (dialogue_preflight or {}).get("summary", {}).get("active_topic"),
        },
        "risks": risks,
        "recommendation": recommendation,
        "route_alternatives": alternatives,
        "selected_alternative": selected,
    }


def _capability_row(registry: CapabilityRegistry, capability_id: str) -> dict[str, Any]:
    capability = registry.capabilities.get(capability_id)
    if capability is None:
        return {"id": capability_id, "status": "missing"}
    return {
        "id": capability.id,
        "status": capability.lifecycle_status,
        "determinism_grade": capability.determinism_grade,
        "side_effects": capability.side_effects,
        "score": list(registry.score_capability(capability)),
    }


def _risks(
    decision: GoalDecision,
    capabilities: list[dict[str, Any]],
    memory_preflight: dict[str, Any],
    dialogue_preflight: dict[str, Any] | None,
) -> list[dict[str, str]]:
    risks: list[dict[str, str]] = []
    if decision.action != "PLAN_WITH_L35":
        risks.append({"code": "non_executable_route", "severity": "info"})
    for capability in capabilities:
        if capability.get("status") == "missing":
            risks.append({"code": f"missing_capability:{capability.get('id')}", "severity": "high"})
        if capability.get("status") == "degraded":
            risks.append({"code": f"degraded_capability:{capability.get('id')}", "severity": "medium"})
        side_effects = dict(capability.get("side_effects", {}))
        if side_effects.get("network") not in {None, "none"}:
            risks.append({"code": f"network_side_effect:{capability.get('id')}", "severity": "medium"})
        if side_effects.get("filesystem") not in {None, "none", "read_only", "write_scoped"}:
            risks.append({"code": f"filesystem_side_effect:{capability.get('id')}", "severity": "medium"})
    if decision.action == "PLAN_WITH_L35" and not decision.required_capabilities:
        risks.append({"code": "open_registry_planning", "severity": "medium"})
    if not memory_preflight.get("template_recommendation"):
        risks.append({"code": "no_mature_memory_template", "severity": "low"})
    if dialogue_preflight is None:
        risks.append({"code": "no_dialogue_context", "severity": "info"})
    return risks


def _recommendation(decision: GoalDecision, risks: list[dict[str, str]]) -> str:
    severities = {risk["severity"] for risk in risks}
    if "high" in severities:
        return "stop_or_request_capability"
    if decision.action == "PLAN_WITH_L35":
        return "continue_to_level35"
    return "return_route_decision"


def _route_alternatives(
    decision: GoalDecision,
    capabilities: list[dict[str, Any]],
    risks: list[dict[str, str]],
    memory_preflight: dict[str, Any],
) -> list[dict[str, Any]]:
    if decision.action == "ASK_CLARIFICATION":
        return [
            _alternative(
                "ask_clarification",
                "L4 terminal",
                "Ask the user for missing goal constraints.",
                risk_score=1,
                cost_score=1,
                confidence_score=90,
                blockers=[],
            )
        ]
    if decision.action == "REQUEST_CAPABILITY_SPEC":
        return [
            _alternative(
                "request_capability_spec",
                "L4 -> L3.2",
                "Request a typed capability spec through Foundry gates.",
                risk_score=2,
                cost_score=3,
                confidence_score=85,
                blockers=[],
            )
        ]
    if decision.action == "STOP_UNSUPPORTED":
        return [
            _alternative(
                "stop_unsupported",
                "L4 terminal",
                "Stop because the goal is unsafe or outside the supported envelope.",
                risk_score=0,
                cost_score=1,
                confidence_score=95,
                blockers=[],
            )
        ]

    blockers = [risk["code"] for risk in risks if risk["severity"] == "high"]
    alternatives: list[dict[str, Any]] = []
    template = memory_preflight.get("template_recommendation")
    if isinstance(template, dict):
        alternatives.append(
            _alternative(
                "memory_template",
                "L4 -> L3.5 template instantiation -> L2",
                "Reuse a mature successful plan shape from runtime memory.",
                risk_score=_risk_score(risks),
                cost_score=1,
                confidence_score=min(98, 70 + int(float(template.get("score", 0.0)) * 20)),
                blockers=blockers,
                evidence={
                    "template_id": template.get("template_id"),
                    "support_count": template.get("support_count"),
                    "safety_status": template.get("safety_status"),
                    "score": template.get("score"),
                },
            )
        )
    if decision.required_capabilities:
        alternatives.append(
            _alternative(
                "deterministic_required_capabilities",
                "L4 -> L3.5 deterministic planner -> L2",
                "Use a known capability chain and deterministic Pipeline DSL validation.",
                risk_score=_risk_score(risks) + (1 if not capabilities else 0),
                cost_score=2,
                confidence_score=82 if not blockers else 20,
                blockers=blockers,
                evidence={"required_capabilities": decision.required_capabilities},
            )
        )
    alternatives.append(
        _alternative(
            "llm_planner_fallback",
            "L4 -> L3.5 local LLM proposal -> validation -> L2",
            "Ask local inference to propose a graph, then validate it deterministically.",
            risk_score=_risk_score(risks) + 2,
            cost_score=4,
            confidence_score=55 if not blockers else 15,
            blockers=blockers,
            evidence={"guardrail": "Pipeline DSL validation required before execution"},
        )
    )
    return alternatives


def _alternative(
    alternative_id: str,
    route: str,
    rationale: str,
    *,
    risk_score: int,
    cost_score: int,
    confidence_score: int,
    blockers: list[str],
    evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    total_score = confidence_score - (risk_score * 10) - (cost_score * 5) - (50 if blockers else 0)
    return {
        "id": alternative_id,
        "route": route,
        "rationale": rationale,
        "risk_score": risk_score,
        "cost_score": cost_score,
        "confidence_score": confidence_score,
        "total_score": total_score,
        "blockers": blockers,
        "evidence": evidence or {},
    }


def _select_alternative(alternatives: list[dict[str, Any]]) -> dict[str, Any] | None:
    available = [item for item in alternatives if not item.get("blockers")]
    candidates = available or alternatives
    if not candidates:
        return None
    selected = sorted(candidates, key=lambda item: (int(item["total_score"]), str(item["id"])), reverse=True)[0]
    return {
        "id": selected["id"],
        "route": selected["route"],
        "total_score": selected["total_score"],
        "reason": "highest_score_without_blockers" if available else "highest_score_with_blockers",
    }


def _risk_score(risks: list[dict[str, str]]) -> int:
    weights = {"info": 0, "low": 1, "medium": 3, "high": 8}
    return sum(weights.get(risk["severity"], 1) for risk in risks)


def _route_label(decision: GoalDecision) -> str:
    if decision.action == "PLAN_WITH_L35":
        return "L4 -> L3.5 -> L2"
    if decision.action == "REQUEST_CAPABILITY_SPEC":
        return "L4 -> L3.2"
    return "L4 terminal"
