"""Helpers for goal-run layer packet payloads."""

from __future__ import annotations


def intent_for_decision(action: str) -> str:
    if action == "PLAN_WITH_L35":
        return "PLAN_GOAL"
    if action == "REQUEST_CAPABILITY_SPEC":
        return "REQUEST_CAPABILITY_SPEC"
    if action == "ASK_CLARIFICATION":
        return "ASK_CLARIFICATION"
    return "STOP_OR_REPORT"


def is_project_analysis(capabilities: list[str]) -> bool:
    return "project_map_report" in capabilities


def expected_artifacts(capabilities: list[str]) -> list[str]:
    artifacts = ["level4_decision", "level35_plan"]
    if is_project_analysis(capabilities):
        artifacts.extend(
            [
                "project_map_report",
                "level35_project_signals",
                "level4_project_interpretation",
                "analysis_tasks",
                "architecture_synthesis",
            ]
        )
    return artifacts


def success_criteria(capabilities: list[str]) -> list[str]:
    if is_project_analysis(capabilities):
        return [
            "project_map_report answers include runtime extraction readiness",
            "level35_project_signals are valid SignalPacket payload",
            "analysis_tasks include proposed extraction or runtime-safety follow-up",
            "architecture_synthesis turns findings into a project-specific first slice",
        ]
    return ["pipeline validates before execution", "execution result is captured in goal report"]


def checkpoint_after(planned: dict[str, object]) -> list[str]:
    nodes = dict(planned.get("pipeline", {})).get("nodes", [])
    checkpointable = {"scan_project_tree", "read_many_files", "extract_python_structure", "project_map_report"}
    return [str(node.get("id")) for node in nodes if isinstance(node, dict) and node.get("capability") in checkpointable]


def process_boundary_for_plan(planned: dict[str, object]) -> list[str]:
    nodes = dict(planned.get("pipeline", {})).get("nodes", [])
    boundary = {"extract_python_structure", "parse_pdf", "fetch_html"}
    return [str(node.get("id")) for node in nodes if isinstance(node, dict) and node.get("capability") in boundary]


def planned_capabilities_active(planned: dict[str, object]) -> bool:
    rows = planned.get("selection", [])
    return all(isinstance(row, dict) and row.get("status") == "active" for row in rows if isinstance(row, dict))
