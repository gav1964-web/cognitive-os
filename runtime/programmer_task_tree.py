"""Build a traceable task graph for the sandbox Programmer Executor."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

from .problem_outcome_contract import problem_outcome_conformance, propagate_problem_outcome_contract

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "knowledge" / "role_qa" / "programmer_task_tree_policy.json"


@lru_cache(maxsize=1)
def load_programmer_task_tree_policy(path: str | None = None) -> dict[str, Any]:
    source = Path(path) if path else POLICY_PATH
    policy = json.loads(source.read_text(encoding="utf-8"))
    if policy.get("schema_version") != "programmer_task_tree_policy.v1":
        raise ValueError("programmer task tree policy must use programmer_task_tree_policy.v1")
    return policy


def build_programmer_task_tree(
    *,
    technical_spec: dict[str, Any],
    implementation_plan: dict[str, Any],
    test_plan: dict[str, Any],
    role_id: str = "task_tree_builder",
) -> dict[str, Any]:
    policy = load_programmer_task_tree_policy()
    target = _target(implementation_plan)
    expected_files = _expected_files(implementation_plan, int(policy["limits"]["expected_files"]))
    blocked = dict(implementation_plan.get("implementation_target") or {}).get("status") == "blocked_no_safe_candidate"
    nodes = _blocked_nodes(implementation_plan, test_plan, policy) if blocked else _work_nodes(implementation_plan, test_plan, policy)
    coverage = _coverage(implementation_plan, test_plan, nodes)
    gates = _verifier_gates(implementation_plan, test_plan, policy)
    problem_contract = propagate_problem_outcome_contract(technical_spec, implementation_plan, test_plan)
    causal_conformance = problem_outcome_conformance(technical_spec, implementation_plan, test_plan)
    ready = bool(
        target and expected_files and not coverage["unmapped_acceptance_ids"]
        and causal_conformance["status"] != "failed"
    )
    return {
        "artifact_type": "ProgrammerTaskTree",
        "role": role_id,
        "status": "ready" if ready else "needs_review",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "authority": "planning_only_no_source_edit",
        "target": target,
        "expected_files": expected_files,
        "source_artifacts": _source_artifacts(technical_spec, implementation_plan, test_plan),
        "problem_outcome_contract": problem_contract,
        "problem_outcome_conformance": causal_conformance,
        "boundary": _boundary(implementation_plan, test_plan, policy),
        "nodes": nodes,
        "coverage": coverage,
        "verifier_gates": gates,
        "stop_conditions": list(policy["stop_conditions"]),
        "programmer_handoff": {
            "next_role": "programmer_executor",
            "allowed_actions": list(policy["allowed_actions"]),
            "forbidden_actions": list(policy["forbidden_actions"]),
            "entry_nodes": [node["id"] for node in nodes if not node["depends_on"]],
        },
        "summary": {
            "node_count": len(nodes),
            "change_node_count": sum(node["kind"] == "change" for node in nodes),
            "acceptance_node_count": sum(node["kind"] == "acceptance" for node in nodes),
            "gate_count": len(gates),
            "dependency_edge_count": sum(len(node["depends_on"]) for node in nodes),
        },
    }


def _work_nodes(plan: dict[str, Any], test_plan: dict[str, Any], policy: dict[str, Any]) -> list[dict[str, Any]]:
    nodes = [_node("SCOPE", "scope", "bind_writable_scope", [], _expected_files(plan, 32), ["ImplementationPlan.writable_scope"])]
    changes = list(plan.get("change_plan") or plan.get("implementation_steps") or [])[: int(policy["limits"]["changes"])]
    previous = "SCOPE"
    for index, change in enumerate(changes, start=1):
        node_id = f"CHANGE-{index:03d}"
        evidence = [f"ImplementationPlan.change_plan.{change.get('id') or index}"]
        nodes.append(
            _node(
                node_id,
                "change",
                str(change.get("kind") or "implement_delta"),
                [previous],
                [str(change.get("target") or "")],
                evidence,
                instruction=str(change.get("instruction") or change.get("action") or ""),
            )
        )
        previous = node_id
    acceptance = _acceptance_rows(plan, test_plan, int(policy["limits"]["acceptance"]))
    acceptance_dependencies = [previous]
    for index, row in enumerate(acceptance, start=1):
        acceptance_id = str(row.get("id") or row.get("acceptance_id") or f"AC-{index:03d}")
        nodes.append(
            _node(
                f"ACCEPT-{index:03d}",
                "acceptance",
                "verify_acceptance",
                acceptance_dependencies,
                [acceptance_id],
                [f"acceptance:{acceptance_id}"],
                acceptance_ids=[acceptance_id],
                instruction=str(row.get("verification") or row.get("criterion") or ""),
            )
        )
    verify_dependencies = [node["id"] for node in nodes if node["kind"] == "acceptance"] or [previous]
    nodes.append(_node("VERIFY", "verification", "run_verifier_gates", verify_dependencies, list(plan.get("verification_commands") or []), ["ImplementationPlan.quality_gates", "TestPlan.executable_acceptance"]))
    nodes.append(_node("HANDOFF", "handoff", "emit_patch_and_test_evidence", ["VERIFY"], ["PatchPackage", "TestResult"], ["ProgrammerTaskTree.coverage"]))
    return nodes


def _blocked_nodes(plan: dict[str, Any], test_plan: dict[str, Any], policy: dict[str, Any]) -> list[dict[str, Any]]:
    reason = str(dict(plan.get("implementation_target") or {}).get("selection_reason") or "no safe bounded target")
    acceptance_ids = [
        str(row.get("id") or row.get("acceptance_id"))
        for row in _acceptance_rows(plan, test_plan, int(policy["limits"]["acceptance"]))
    ]
    return [
        _node(
            "BLOCKED",
            "stop",
            "preserve_no_patch_handoff",
            [],
            [reason],
            ["ImplementationPlan.implementation_target"],
            acceptance_ids=acceptance_ids,
            status="needs_review",
            stop_conditions=list(policy["stop_conditions"]),
        )
    ]


def _node(
    node_id: str,
    kind: str,
    action: str,
    depends_on: list[str],
    inputs: list[str],
    evidence_refs: list[str],
    *,
    instruction: str = "",
    acceptance_ids: list[str] | None = None,
    status: str = "ready",
    stop_conditions: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "id": node_id,
        "kind": kind,
        "action": action,
        "owner": "programmer_executor" if kind not in {"scope", "stop"} else "task_tree_builder",
        "status": status,
        "depends_on": depends_on,
        "inputs": [item for item in inputs if item],
        "instruction": instruction,
        "acceptance_ids": list(acceptance_ids or []),
        "evidence_refs": evidence_refs,
        "stop_conditions": list(stop_conditions or []),
        "source_code_changes_allowed": False,
    }


def _coverage(plan: dict[str, Any], test_plan: dict[str, Any], nodes: list[dict[str, Any]]) -> dict[str, Any]:
    expected = [str(row.get("id") or row.get("acceptance_id")) for row in _acceptance_rows(plan, test_plan, 100)]
    mapped = [item for node in nodes for item in node.get("acceptance_ids", [])]
    change_refs = [str(row.get("id")) for row in list(plan.get("change_plan") or []) if row.get("id")]
    blocked = any(node["kind"] == "stop" for node in nodes)
    return {
        "acceptance_ids": expected,
        "mapped_acceptance_ids": mapped,
        "unmapped_acceptance_ids": [item for item in expected if item not in mapped],
        "change_ids": change_refs,
        "all_changes_traced": blocked or len([node for node in nodes if node["kind"] == "change"]) >= min(len(change_refs), 12),
    }


def _acceptance_rows(plan: dict[str, Any], test_plan: dict[str, Any], limit: int) -> list[dict[str, Any]]:
    rows = list(plan.get("acceptance_mapping") or [])
    if not rows:
        rows = list(dict(test_plan.get("executable_acceptance") or {}).get("obligations") or [])
    return [dict(row) for row in rows if isinstance(row, dict)][:limit]


def _verifier_gates(plan: dict[str, Any], test_plan: dict[str, Any], policy: dict[str, Any]) -> list[dict[str, Any]]:
    gates = [{"id": gate_id, "status": "required"} for gate_id in policy["required_gates"]]
    gates.extend(
        {"id": str(row.get("id") or row.get("name")), "status": "required"}
        for row in list(plan.get("quality_gates") or [])
        if row.get("id") or row.get("name")
    )
    if _acceptance_rows(plan, test_plan, 1):
        gates.append({"id": "executable_acceptance", "status": "required"})
    return _dedupe_by_id(gates)


def _boundary(plan: dict[str, Any], test_plan: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    blocked = dict(plan.get("implementation_target") or {}).get("status") == "blocked_no_safe_candidate"
    dependency = dict(plan.get("dependency_policy") or {})
    return {
        "track": "blocked_handoff" if blocked else "sandbox_patch_tree",
        "target_bound": bool(_target(plan)),
        "expected_file_count": len(_expected_files(plan, 32)),
        "acceptance_obligation_count": len(_acceptance_rows(plan, test_plan, 100)),
        "dependency_policy": dependency.get("new_runtime_dependencies", "unknown"),
        "requires_dependency_profile": dependency.get("new_runtime_dependencies") not in {None, "forbidden_by_default"},
        "requires_fixture_profile": bool(dict(test_plan.get("fixture_policy") or {})),
        "max_nodes": int(policy["limits"]["max_nodes"]),
    }


def _source_artifacts(*artifacts: dict[str, Any]) -> list[dict[str, Any]]:
    return [{"type": artifact.get("artifact_type"), "role": artifact.get("role")} for artifact in artifacts]


def _target(plan: dict[str, Any]) -> str:
    intent = dict(plan.get("patch_intent") or {})
    return str(intent.get("target_symbol") or dict(plan.get("implementation_target") or {}).get("candidate") or "")


def _expected_files(plan: dict[str, Any], limit: int) -> list[str]:
    files: list[str] = []
    for item in plan.get("expected_files", []):
        path = str(item).split(":", 1)[0]
        if path and path not in files:
            files.append(path)
    return files[:limit]


def _dedupe_by_id(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    result = []
    for row in rows:
        row_id = str(row["id"])
        if row_id not in seen:
            seen.add(row_id)
            result.append(row)
    return result
