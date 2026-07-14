"""Layer 3.5 spinal planner contract.

This module is the motor translation boundary between L4 semantic decisions
and L2 execution. It returns typed packets and validated Pipeline DSL, but it
does not execute plugins or mutate the Capability Registry.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from .deterministic_goal_planner import plan_from_required_capabilities
from .graph_planner import GraphPlanningError, plan_pipeline
from .layer_packets import motor_plan_packet, signal_packet, validate_packet
from .llm_graph_planner import plan_pipeline_with_llm
from .local_inference import LocalInferenceConfig, LocalInferenceError
from .models import Pipeline, PolicyDecision
from .pipeline import PipelineValidationError, validate_pipeline
from .planner_stub import plan_recovery
from .registry import CapabilityRegistry
from .template_instantiator import TemplateInstantiationError, plan_from_memory_template


class SpinalPlanningError(RuntimeError):
    """Raised when Layer 3.5 cannot build a valid motor plan."""


def plan_from_intent_packet(
    intent: dict[str, Any],
    registry: CapabilityRegistry,
    *,
    allow_local_llm: bool = False,
    config: LocalInferenceConfig | None = None,
    memory_hint: dict[str, Any] | None = None,
    memory_preflight: dict[str, Any] | None = None,
    required_capabilities: list[str] | None = None,
) -> dict[str, Any]:
    """Translate L4 IntentPacket into a validated L2 MotorPlanPacket.

    Deterministic rules are tried first. The local LLM planner is only used as
    a bounded proposal source when explicitly enabled. Either route must pass
    Pipeline DSL validation before a motor plan packet is emitted.
    """

    validate_packet(intent)
    if intent["packet_type"] != "INTENT" or intent["source_layer"] != "L4" or intent["target_layer"] != "L3.5":
        raise SpinalPlanningError("spinal planner accepts only L4 -> L3.5 IntentPacket")

    payload = dict(intent["payload"])
    correlation_id = str(intent["correlation_id"])
    goal = _goal_key(payload)
    errors: list[str] = []
    required = [str(item) for item in (required_capabilities or [])]
    diagnostics = _selection_diagnostics(registry)

    if memory_preflight:
        try:
            planned = plan_from_memory_template(
                str(payload.get("objective") or goal),
                memory_preflight,
                registry,
                required_capabilities=required,
            )
            if planned is not None:
                return _planned_dict_result(correlation_id, goal, planned, registry, diagnostics=diagnostics)
        except TemplateInstantiationError as exc:
            errors.append(f"memory_template: {exc}")

    if required:
        planned = plan_from_required_capabilities(
            str(payload.get("objective") or goal),
            required,
            registry,
        )
        if planned is not None:
            return _planned_dict_result(correlation_id, goal, planned, registry, diagnostics=diagnostics)

    try:
        pipeline = plan_pipeline(goal, registry)
        validate_pipeline(pipeline, registry)
        return _planned_result(
            correlation_id=correlation_id,
            planner="deterministic_graph_planner",
            goal=goal,
            pipeline=pipeline,
            selection=[],
            diagnostics=diagnostics,
            signals=[
                {
                    "type": "MOTOR_PLAN_READY",
                    "goal": goal,
                    "planner": "deterministic_graph_planner",
                    "confidence": "high",
                }
            ],
        )
    except (GraphPlanningError, PipelineValidationError) as exc:
        errors.append(str(exc))

    if allow_local_llm:
        try:
            llm_result = plan_pipeline_with_llm(
                str(payload.get("objective") or goal),
                registry,
                config=config,
                memory_hint=memory_hint,
            )
            pipeline = _pipeline_from_dict(dict(llm_result["pipeline"]))
            validate_pipeline(pipeline, registry)
            return _planned_result(
                correlation_id=correlation_id,
                planner="local_llm_graph_planner",
                goal=goal,
                pipeline=pipeline,
                selection=list(llm_result.get("selection", [])),
                diagnostics={
                    **diagnostics,
                    "llm_fallback": {
                        "invoked": True,
                        "reason": "deterministic_route_failed",
                        "authority": "proposal_only_validated_by_pipeline_dsl",
                    },
                },
                signals=[
                    {
                        "type": "MOTOR_PLAN_READY",
                        "goal": goal,
                        "planner": "local_llm_graph_planner",
                        "confidence": "medium",
                    }
                ],
                proposal=dict(llm_result.get("proposal", {})),
            )
        except (LocalInferenceError, GraphPlanningError, PipelineValidationError, KeyError, TypeError) as exc:
            errors.append(str(exc))

    signal = signal_packet(
        correlation_id=correlation_id,
        signals=[
            {
                "type": "NEEDS_L4_DECISION",
                "reason": "NO_VALID_MOTOR_PLAN",
                "goal": goal,
                "errors": errors,
            }
        ],
        needs_l4_decision=True,
        blocked=True,
    )
    return {
        "status": "blocked",
        "goal": goal,
        "planner": "spinal_planner",
        "motor_plan_packet": None,
        "pipeline": None,
        "signal_packet": signal,
        "errors": errors,
        "selection_diagnostics": {
            **diagnostics,
            "llm_fallback": {
                "allowed": allow_local_llm,
                "invoked": False,
                "reason": "no_valid_model_or_deterministic_plan",
            },
        },
    }


def adapt_from_interrupt_packet(interrupt: dict[str, Any], registry: CapabilityRegistry) -> dict[str, Any]:
    """Translate L2 InterruptPacket into a bounded local motor decision."""

    validate_packet(interrupt)
    if interrupt["packet_type"] != "INTERRUPT" or interrupt["source_layer"] != "L2" or interrupt["target_layer"] != "L3.5":
        raise SpinalPlanningError("spinal planner accepts only L2 -> L3.5 InterruptPacket for adaptation")

    correlation_id = str(interrupt["correlation_id"])
    decision = plan_recovery(dict(interrupt["payload"]), registry)
    needs_l4 = decision.action in {"GENERATE_SPEC", "STOP"}
    blocked = decision.action == "STOP"
    signal = signal_packet(
        correlation_id=correlation_id,
        signals=[_decision_signal(decision)],
        needs_l4_decision=needs_l4,
        blocked=blocked,
    )
    return {
        "status": "adapted" if not blocked else "blocked",
        "decision": asdict(decision),
        "signal_packet": signal,
    }


def _planned_result(
    *,
    correlation_id: str,
    planner: str,
    goal: str,
    pipeline: Pipeline,
    selection: list[dict[str, Any]],
    diagnostics: dict[str, Any] | None = None,
    signals: list[dict[str, Any]],
    proposal: dict[str, Any] | None = None,
) -> dict[str, Any]:
    packet = motor_plan_packet(
        correlation_id=correlation_id,
        planner=planner,
        capability_chain=[node.capability for node in pipeline.nodes],
        execution_policy={
            "pipeline_id": pipeline.id,
            "retry_policy": pipeline.retry_policy,
            "validate_before_execution": True,
            "execute_plugins": False,
        },
        validation={
            "pipeline_dsl_validated": True,
            "registry_validated": True,
            "selection": selection,
        },
    )
    return {
        "status": "planned",
        "goal": goal,
        "planner": planner,
        "motor_plan_packet": packet,
        "pipeline": _pipeline_to_dict(pipeline),
        "signal_packet": signal_packet(correlation_id=correlation_id, signals=signals),
        "proposal": proposal or {},
        "selection_diagnostics": diagnostics or {},
    }


def _planned_dict_result(
    correlation_id: str,
    goal: str,
    planned: dict[str, Any],
    registry: CapabilityRegistry,
    diagnostics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    pipeline = _pipeline_from_dict(dict(planned["pipeline"]))
    validate_pipeline(pipeline, registry)
    planner = str(planned.get("planner") or "unknown")
    result = _planned_result(
        correlation_id=correlation_id,
        planner=planner,
        goal=goal,
        pipeline=pipeline,
        selection=list(planned.get("selection", [])),
        diagnostics=diagnostics,
        signals=[
            {
                "type": "MOTOR_PLAN_READY",
                "goal": goal,
                "planner": planner,
                "confidence": "high",
            }
        ],
        proposal=dict(planned.get("proposal", {})),
    )
    for key in ("template_id", "template_support_count"):
        if key in planned:
            result[key] = planned[key]
    return result


def _selection_diagnostics(registry: CapabilityRegistry) -> dict[str, Any]:
    rows = []
    active = 0
    degraded = 0
    blocked = 0
    deterministic = 0
    side_effect_free = 0
    for capability in sorted(registry.capabilities.values(), key=registry.score_capability, reverse=True):
        status = capability.lifecycle_status
        if status == "active":
            active += 1
        elif status == "degraded":
            degraded += 1
        else:
            blocked += 1
        if capability.determinism_grade in {"A", "B"}:
            deterministic += 1
        if capability.side_effects.get("filesystem") == "none" and capability.side_effects.get("network") == "none":
            side_effect_free += 1
        rows.append(
            {
                "capability_id": capability.id,
                "status": status,
                "determinism_grade": capability.determinism_grade,
                "side_effects": capability.side_effects,
                "score": list(registry.score_capability(capability)),
                "selectable": status in {"active", "degraded"},
            }
        )
    return {
        "selection_policy": "status_then_determinism_then_side_effects_then_quality_then_latency",
        "schema_policy": "Pipeline DSL validation is mandatory before MotorPlanPacket emission",
        "summary": {
            "capability_count": len(rows),
            "active": active,
            "degraded": degraded,
            "blocked": blocked,
            "deterministic_grade_ab": deterministic,
            "side_effect_free": side_effect_free,
        },
        "top_candidates": rows[:10],
    }


def _goal_key(payload: dict[str, Any]) -> str:
    constraints = payload.get("constraints")
    if isinstance(constraints, dict):
        for key in ("route_goal", "pipeline_id", "goal_key"):
            if constraints.get(key):
                return str(constraints[key])
    intent = str(payload.get("intent", "")).strip()
    if intent in {
        "normalize_then_hash",
        "select_then_hash",
        "markdown_file_to_text_file",
        "markdown_file_to_rtf_file",
        "fetch_links",
        "spreadsheet_to_csv",
        "csv_to_spreadsheet",
    }:
        return intent
    return str(payload.get("objective") or intent or "unknown").strip()


def _pipeline_to_dict(pipeline: Pipeline) -> dict[str, Any]:
    return {
        "id": pipeline.id,
        "version": pipeline.version,
        "nodes": [asdict(node) for node in pipeline.nodes],
        "edges": pipeline.edges,
        "retry_policy": pipeline.retry_policy,
    }


def _pipeline_from_dict(data: dict[str, Any]) -> Pipeline:
    from .models import PipelineNode

    return Pipeline(
        id=str(data["id"]),
        version=str(data["version"]),
        nodes=[
            PipelineNode(
                id=str(item["id"]),
                capability=str(item["capability"]),
                input=dict(item.get("input", {})),
            )
            for item in data["nodes"]
        ],
        edges=[list(edge) for edge in data.get("edges", [])],
        retry_policy=dict(data.get("retry_policy", {"max_attempts": 1, "retry_on": ["transient"]})),
    )


def _decision_signal(decision: PolicyDecision) -> dict[str, Any]:
    signal = {
        "type": "MOTOR_ADAPTATION",
        "action": decision.action,
        "reason_code": decision.reason_code,
    }
    if decision.replacement_capability:
        signal["replacement_capability"] = decision.replacement_capability
    return signal
