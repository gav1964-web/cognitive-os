"""Deterministic evaluation corpus for the Layer 3.5 spinal planner."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from .contract_registry import ContractRegistry
from .layer_packets import intent_packet, interrupt_packet
from .registry import CapabilityRegistry
from .spinal_planner import adapt_from_interrupt_packet
from .spinal_quality import score_spinal_result
from .goal_runtime import plan_motor_route


PLAN_CASES = [
    {
        "id": "normalize_hash_required_chain",
        "objective": "Normalize and hash text",
        "intent": "PLAN_KNOWN_ROUTE",
        "required": ["normalize_text", "hash_payload"],
        "expected_status": "planned",
        "expected_planner": "deterministic_required_capabilities",
    },
    {
        "id": "list_files_required_chain",
        "objective": "List files in a directory",
        "intent": "PLAN_KNOWN_ROUTE",
        "required": ["list_files"],
        "expected_status": "planned",
        "expected_planner": "deterministic_required_capabilities",
    },
    {
        "id": "project_analysis_chain",
        "objective": "Analyze a Python project and produce a project map",
        "intent": "ANALYZE_PROJECT",
        "required": [
            "scan_project_tree",
            "detect_project_stack",
            "read_many_files",
            "extract_python_structure",
            "extract_runtime_commands",
            "project_map_report",
        ],
        "expected_status": "planned",
        "expected_planner": "deterministic_required_capabilities",
    },
    {
        "id": "graph_rule_route",
        "objective": "Normalize and hash text",
        "intent": "normalize_then_hash",
        "route_goal": "normalize_then_hash",
        "required": [],
        "expected_status": "planned",
        "expected_planner": "deterministic_graph_planner",
    },
    {
        "id": "unknown_route_blocks",
        "objective": "Perform an unavailable physical operation",
        "intent": "UNKNOWN_OPERATION",
        "required": [],
        "expected_status": "blocked",
        "expected_planner": "spinal_planner",
    },
]


RECOVERY_CASES = [
    {
        "id": "transient_retry",
        "capability_id": "fetch_html",
        "error_class": "transient",
        "capability_status": "active",
        "expected_action": "RETRY",
    },
    {
        "id": "quarantined_fallback",
        "capability_id": "parse_title",
        "error_class": "dependency_error",
        "capability_status": "quarantined",
        "expected_action": "SWITCH_PLUGIN",
    },
    {
        "id": "unknown_failure_escalates",
        "capability_id": "normalize_text",
        "error_class": "runtime_bug",
        "capability_status": "active",
        "expected_action": "STOP",
    },
]


def run_spinal_benchmark(root: Path) -> dict[str, Any]:
    registry = CapabilityRegistry(root)
    registry.load()
    contracts = ContractRegistry.from_capability_registry(registry)
    planning = [_run_plan_case(case, registry, contracts) for case in PLAN_CASES]
    recovery = [_run_recovery_case(case, registry, contracts) for case in RECOVERY_CASES]
    all_passed = all(case["passed"] for case in planning + recovery)
    planned_cases = [case for case in planning if case["expected_status"] == "planned"]
    blocked_cases = [case for case in planning if case["expected_status"] == "blocked"]
    return {
        "status": "ok" if all_passed else "failed",
        "benchmark": "Layer 3.5 Vertical Planning v0.2",
        "planning_cases": planning,
        "recovery_cases": recovery,
        "summary": {
            "case_count": len(planning) + len(recovery),
            "passed": sum(1 for case in planning + recovery if case["passed"]),
            "route_accuracy": _rate(case["route_match"] for case in planning),
            "quality_gate_rate": _rate(case["quality_passed"] for case in planning),
            "packet_contract_rate": _rate(case["packet_contracts_valid"] for case in planning + recovery),
            "recovery_accuracy": _rate(case["action_match"] for case in recovery),
            "blocked_safety_rate": _rate(case["route_match"] for case in blocked_cases),
            "planned_route_rate": _rate(case["route_match"] for case in planned_cases),
            "avg_planning_latency_ms": round(
                sum(float(case["latency_ms"]) for case in planning) / len(planning), 3
            ),
            "llm_invocations": 0,
        },
    }


def _run_plan_case(
    case: dict[str, Any],
    registry: CapabilityRegistry,
    contracts: ContractRegistry,
) -> dict[str, Any]:
    packet = intent_packet(
        correlation_id=f"benchmark_{case['id']}",
        intent=str(case["intent"]),
        objective=str(case["objective"]),
        constraints={"route_goal": case.get("route_goal")} if case.get("route_goal") else {},
        expected_artifacts=[],
        success_criteria=["validated route or controlled block"],
    )
    started = time.perf_counter()
    result = plan_motor_route(
        packet,
        registry,
        required_capabilities=list(case["required"]),
        allow_local_llm=False,
    )
    latency_ms = (time.perf_counter() - started) * 1000
    quality = score_spinal_result(result, registry)
    packet_contracts_valid = _validate_result_packets(result, contracts)
    route_match = (
        result.get("status") == case["expected_status"]
        and result.get("planner") == case["expected_planner"]
    )
    return {
        "id": case["id"],
        "expected_status": case["expected_status"],
        "actual_status": result.get("status"),
        "expected_planner": case["expected_planner"],
        "actual_planner": result.get("planner"),
        "route_match": route_match,
        "quality_score": quality["score"],
        "quality_passed": quality["passed"],
        "packet_contracts_valid": packet_contracts_valid,
        "latency_ms": round(latency_ms, 3),
        "passed": route_match and quality["passed"] and packet_contracts_valid,
    }


def _run_recovery_case(
    case: dict[str, Any],
    registry: CapabilityRegistry,
    contracts: ContractRegistry,
) -> dict[str, Any]:
    raw = {
        "type": "CRITICAL_INTERRUPT",
        "pipeline_id": f"benchmark_{case['id']}",
        "failed_node_id": "node_1",
        "capability_id": case["capability_id"],
        "error_class": case["error_class"],
        "error_fingerprint": {"exception_type": "BenchmarkError", "traceback_hash": "benchmark"},
        "state_ref": "checkpoint_benchmark",
        "capability_status": case["capability_status"],
        "suggested_actions": ["RETRY", "SWITCH_PLUGIN", "GENERATE_SPEC", "STOP"],
    }
    packet = interrupt_packet(correlation_id=f"benchmark_{case['id']}", interrupt=raw)
    contracts.validate_layer_packet(packet)
    result = adapt_from_interrupt_packet(packet, registry)
    contracts.validate_layer_packet(dict(result["signal_packet"]))
    actual_action = dict(result["decision"])["action"]
    action_match = actual_action == case["expected_action"]
    return {
        "id": case["id"],
        "expected_action": case["expected_action"],
        "actual_action": actual_action,
        "action_match": action_match,
        "packet_contracts_valid": True,
        "passed": action_match,
    }


def _validate_result_packets(result: dict[str, Any], contracts: ContractRegistry) -> bool:
    try:
        for key in ("motor_plan_packet", "signal_packet"):
            packet = result.get(key)
            if isinstance(packet, dict):
                contracts.validate_layer_packet(packet)
        return True
    except (ValueError, TypeError):
        return False


def _rate(values: Any) -> float:
    items = list(values)
    return round(sum(1 for value in items if value) / len(items), 3) if items else 1.0
