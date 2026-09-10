"""Goal report construction."""

from __future__ import annotations

from typing import Any


def build_goal_report(session: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    decision = dict(payload.get("level4_decision", {}))
    execution = dict(payload.get("execution", {}))
    plan = dict(payload.get("level35_plan", {}))
    summary = _summary(decision, execution, plan)
    return {
        "goal_id": session["goal_id"],
        "goal": session["goal"],
        "status": payload.get("status", "unknown"),
        "summary": summary,
        "goal_intake": payload.get("goal_intake"),
        "dialogue_preflight": payload.get("dialogue_preflight"),
        "memory_preflight": payload.get("memory_preflight"),
        "knowledge_preflight": payload.get("knowledge_preflight"),
        "knowledge_gaps": payload.get("knowledge_gaps", []),
        "knowledge_artifacts": payload.get("knowledge_artifacts", []),
        "level4_decision": decision,
        "level4_deliberation": payload.get("level4_deliberation"),
        "layer_packets": payload.get("layer_packets", []),
        "level35_plan": plan,
        "execution": execution,
        "level35_project_signals": payload.get("level35_project_signals"),
        "level4_project_interpretation": payload.get("level4_project_interpretation"),
        "analysis_tasks": payload.get("analysis_tasks"),
        "architecture_synthesis": payload.get("architecture_synthesis"),
        "llm_interpretation": payload.get("llm_interpretation"),
        "clarifications": session.get("clarifications", []),
        "events": session.get("events", []),
    }


def _summary(decision: dict[str, Any], execution: dict[str, Any], plan: dict[str, Any]) -> str:
    action = decision.get("action")
    if action == "ASK_CLARIFICATION":
        return f"Clarification needed: {decision.get('clarification_question')}"
    if action == "REQUEST_CAPABILITY_SPEC":
        return f"Capability spec requested: {decision.get('missing_capability_hint')}"
    if action == "STOP_UNSUPPORTED":
        return "Goal stopped as unsupported or unsafe."
    if execution.get("status") == "ok":
        completed = ", ".join(execution.get("completed_nodes", []))
        return f"Goal executed successfully through nodes: {completed}"
    if plan.get("status") == "planned":
        return "Goal planned successfully; execution was not requested."
    return "Goal route decided."
