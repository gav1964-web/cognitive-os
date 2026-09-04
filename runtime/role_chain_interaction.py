"""Measure continuity and control decisions across the role chain."""

from __future__ import annotations

import hashlib
import json
from typing import Any


PRIMARY_ROLE_SEQUENCE = (
    "project_analyzer",
    "architect",
    "spec_writer",
    "implementer",
    "tester",
    "reviewer",
)


def build_role_chain_trace(
    *, project: str, result: dict[str, Any], minimum_score: float = 0.9
) -> dict[str, Any]:
    """Build one measured trace from a completed known-project role pipeline."""
    gate_cases = {
        str(row.get("role_id")): dict(row)
        for row in dict(result.get("role_gates") or {}).get("cases", [])
        if isinstance(row, dict)
    }
    quality = dict(result.get("role_quality") or {})
    control = dict(result.get("cognitive_control_plane") or {})
    promotion = dict(control.get("artifact_promotion_gate") or {})
    telemetry = dict(result.get("chain_telemetry") or {})
    build_reselections = list(telemetry.get("build_reselection_history") or [])
    execution_reselections = list(telemetry.get("execution_reselection_history") or [])
    recovery = dict(telemetry.get("no_safe_candidate_recovery") or {})
    controlled_block = bool(
        quality.get("implementation_blocked_no_safe_candidate") is True
        and quality.get("test_blocked_no_safe_candidate") is True
        and quality.get("review_target") == "blocked_no_safe_candidate"
        and result.get("next_action") == "rework_role_artifacts"
    )
    checks = {
        **{
            f"{role_id}_gate_passed": dict(gate_cases.get(role_id) or {}).get("status") == "ok"
            for role_id in PRIMARY_ROLE_SEQUENCE
        },
        "spec_to_implementer_target_preserved": quality.get("implementation_targets_extraction_candidate") is True
        or controlled_block,
        "implementer_to_tester_target_preserved": quality.get("test_targets_implementation_target") is True,
        "tester_to_reviewer_target_preserved": quality.get("review_targets_implementation_target") is True,
        "review_confirms_target_coverage": quality.get("review_confirms_target_coverage") is True,
        "control_plane_promotion_gate_passed": promotion.get("status") == "passed",
    }
    score = round(sum(checks.values()) / len(checks), 4)
    intervention_reasons = []
    if result.get("next_action") == "review_risks_then_run_project_transform":
        intervention_reasons.append("material_risk_review")
    if dict(control.get("semantic_escalation") or {}).get("l4_5_required") is True:
        intervention_reasons.append("semantic_escalation")
    if any(dict(gate_cases.get(role) or {}).get("status") == "failed" for role in PRIMARY_ROLE_SEQUENCE):
        intervention_reasons.append("failed_role_gate")
    if controlled_block:
        intervention_reasons.append("bounded_rework_after_no_safe_candidate")
    recovery_ready = recovery.get("status") == "bounded_rework_ready"
    handoff_loss = [name for name, passed in checks.items() if not passed]
    handoffs = _handoff_contracts(checks=checks, selected_target=quality.get("selected_extraction_candidate"))
    arbitration = _arbitration_metrics(dict(telemetry.get("candidate_arbitration") or {}))
    uncertainties = _unresolved_uncertainties(
        arbitration=arbitration,
        semantic_escalation=dict(control.get("semantic_escalation") or {}),
        intervention_reasons=intervention_reasons,
    )
    status = "controlled_stop" if controlled_block and not handoff_loss else (
        "ok" if score >= minimum_score and not handoff_loss else "needs_work"
    )
    return {
        "artifact_type": "RoleChainInteractionTrace",
        "project": project,
        "status": status,
        "route_kind": "known_project",
        "route": list(PRIMARY_ROLE_SEQUENCE) + (["researcher", "architect"] if recovery_ready else []),
        "conditional_roles": {
            "researcher": "semantic_recovery" if recovery_ready else "not_required_for_known_project",
            "developer": "bounded_decomposition_required" if recovery_ready else "not_required",
        },
        "checks": checks,
        "interaction_score": score,
        "handoff_loss_count": len(handoff_loss),
        "handoff_loss": handoff_loss,
        "handoff_contracts": handoffs,
        "arbitration_metrics": arbitration,
        "unresolved_uncertainties": uncertainties,
        "reselection_count": len(build_reselections) + len(execution_reselections),
        "build_reselection_history": build_reselections,
        "execution_reselection_history": execution_reselections,
        "review_risk_summary": dict(telemetry.get("review_risk_summary") or {}),
        "required_human_decision_count": len(intervention_reasons),
        "required_human_decisions": intervention_reasons,
        "first_pass_acceptance": not handoff_loss and not build_reselections and not execution_reselections,
        "selected_target": quality.get("selected_extraction_candidate"),
        "final_review_target": quality.get("review_target"),
        "next_action": result.get("next_action"),
        "terminal_reason": "no_safe_candidate_after_bounded_reselection" if controlled_block else None,
        "recovery_status": recovery.get("status"),
        "recovery_candidate_status": recovery.get("candidate_status"),
    }


def build_unknown_role_chain_trace(
    *, intake: dict[str, Any], candidate: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Represent a controlled unknown stop as a valid conditional role route."""
    routing = dict(intake.get("routing") or {})
    plan = dict(intake.get("research_plan") or {})
    candidate_status = str(dict(candidate or {}).get("status") or "not_created")
    promotion_gate = dict(dict(candidate or {}).get("promotion_gate") or {})
    checks = {
        "analyzer_detected_unknown": routing.get("current_stratum") == "unknown_new_archetype",
        "researcher_received_typed_gap": bool(dict(intake.get("knowledge_gap") or {}).get("gap_id")),
        "research_plan_is_bounded": bool(plan.get("steps"))
        and dict(plan.get("policy") or {}).get("llm_may_not_browse_freely") is True,
        "downstream_roles_are_quarantined": routing.get("downstream_roles_blocked") is True,
        "candidate_did_not_auto_promote": promotion_gate.get("automatic_promotion") is not True,
    }
    score = round(sum(checks.values()) / len(checks), 4)
    handoff_body = {
        "producer": "project_analyzer",
        "consumer": "researcher",
        "target": dict(intake.get("knowledge_gap") or {}).get("gap_id"),
        "producer_gate": "analyzer_detected_unknown",
        "continuity_gate": "researcher_received_typed_gap",
    }
    handoff_passed = checks["analyzer_detected_unknown"] and checks["researcher_received_typed_gap"]
    return {
        "artifact_type": "RoleChainInteractionTrace",
        "project": intake.get("project"),
        "status": "controlled_stop" if all(checks.values()) else "needs_work",
        "route_kind": "unknown_project",
        "route": ["project_analyzer", "researcher"],
        "blocked_route": ["architect", "spec_writer", "implementer", "tester", "reviewer"],
        "checks": checks,
        "interaction_score": score,
        "handoff_loss_count": sum(not value for value in checks.values()),
        "handoff_contracts": [{
            **handoff_body,
            "status": "preserved" if handoff_passed else "lost",
            "loss_reason": None if handoff_passed else "unknown_intake_contract_incomplete",
            "contract_digest": _digest(handoff_body),
        }],
        "arbitration_metrics": _arbitration_metrics({}),
        "unresolved_uncertainties": ["project_archetype_unresolved"],
        "reselection_count": 0,
        "required_human_decision_count": int(candidate_status in {
            "needs_teacher_approval", "needs_codex_approval", "ready_for_human_merge",
        }),
        "first_pass_acceptance": False,
        "terminal_reason": "unknown_archetype_quarantine",
        "candidate_status": candidate_status,
    }


def summarize_role_chain_traces(traces: list[dict[str, Any]]) -> dict[str, Any]:
    scores = [float(row.get("interaction_score") or 0.0) for row in traces]
    known = [row for row in traces if row.get("route_kind") != "unknown_project"]
    return {
        "trace_count": len(traces),
        "minimum_interaction_score": min(scores, default=0.0),
        "handoff_loss_count": sum(int(row.get("handoff_loss_count") or 0) for row in traces),
        "reselection_count": sum(int(row.get("reselection_count") or 0) for row in traces),
        "required_human_decision_count": sum(int(row.get("required_human_decision_count") or 0) for row in traces),
        "arbitration_eligible_count": sum(
            dict(row.get("arbitration_metrics") or {}).get("eligible") is True for row in traces
        ),
        "arbitration_invoked_count": sum(
            dict(row.get("arbitration_metrics") or {}).get("invoked") is True for row in traces
        ),
        "arbitration_override_count": sum(
            dict(row.get("arbitration_metrics") or {}).get("accepted_override") is True for row in traces
        ),
        "unresolved_uncertainty_count": sum(len(row.get("unresolved_uncertainties") or []) for row in traces),
        "first_pass_acceptance_count": sum(row.get("first_pass_acceptance") is True for row in known),
        "known_trace_count": len(known),
        "controlled_unknown_stop_count": sum(
            row.get("status") == "controlled_stop" and row.get("route_kind") == "unknown_project"
            for row in traces
        ),
        "controlled_known_stop_count": sum(
            row.get("status") == "controlled_stop" and row.get("route_kind") == "known_project"
            for row in traces
        ),
        "bounded_recovery_ready_count": sum(
            row.get("recovery_status") == "bounded_rework_ready" for row in traces
        ),
    }


def _handoff_contracts(*, checks: dict[str, bool], selected_target: Any) -> list[dict[str, Any]]:
    definitions = (
        ("project_analyzer", "architect", "project_analyzer_gate_passed", "architect_gate_passed"),
        ("architect", "spec_writer", "architect_gate_passed", "spec_writer_gate_passed"),
        ("spec_writer", "implementer", "spec_writer_gate_passed", "spec_to_implementer_target_preserved"),
        ("implementer", "tester", "implementer_gate_passed", "implementer_to_tester_target_preserved"),
        ("tester", "reviewer", "tester_gate_passed", "tester_to_reviewer_target_preserved"),
    )
    rows = []
    for producer, consumer, producer_check, continuity_check in definitions:
        passed = checks.get(producer_check) is True and checks.get(continuity_check) is True
        body = {
            "producer": producer,
            "consumer": consumer,
            "target": selected_target,
            "producer_gate": producer_check,
            "continuity_gate": continuity_check,
        }
        rows.append({
            **body,
            "status": "preserved" if passed else "lost",
            "loss_reason": None if passed else next(
                name for name in (producer_check, continuity_check) if checks.get(name) is not True
            ),
            "contract_digest": _digest(body),
        })
    return rows


def _arbitration_metrics(advisory: dict[str, Any]) -> dict[str, Any]:
    return {
        "source": advisory.get("source") or "deterministic",
        "eligible": advisory.get("eligible") is True,
        "invoked": advisory.get("llm_invoked") is True,
        "accepted_override": advisory.get("accepted") is True,
        "selected_source": advisory.get("selected_source"),
        "fallback_used": advisory.get("source") == "deterministic_fallback",
    }


def _unresolved_uncertainties(
    *, arbitration: dict[str, Any], semantic_escalation: dict[str, Any], intervention_reasons: list[str]
) -> list[str]:
    uncertainties = []
    if semantic_escalation.get("l4_5_required") is True:
        uncertainties.append("semantic_escalation_pending")
    if arbitration.get("fallback_used") is True:
        uncertainties.append("candidate_arbitration_unavailable")
    if "material_risk_review" in intervention_reasons:
        uncertainties.append("material_risk_requires_human_review")
    return uncertainties


def _digest(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()
