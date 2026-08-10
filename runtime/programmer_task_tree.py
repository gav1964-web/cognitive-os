"""Task decomposition for the sandbox Programmer Executor."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def build_programmer_task_tree(
    *,
    technical_spec: dict[str, Any],
    implementation_plan: dict[str, Any],
    test_plan: dict[str, Any],
) -> dict[str, Any]:
    target = _target(implementation_plan)
    expected_files = _expected_files(implementation_plan)
    contract = dict(dict(implementation_plan.get("contract_binding") or {}).get("input_contract") or {})
    obligations = list(dict(test_plan.get("executable_acceptance") or {}).get("obligations") or [])
    gates = _verifier_gates(implementation_plan, obligations)
    nodes = _nodes(target, expected_files, contract, obligations, gates)
    return {
        "artifact_type": "ProgrammerTaskTree",
        "role": "programmer_task_builder",
        "status": "ready" if target and expected_files else "needs_review",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "authority": "planning_only_no_source_edit",
        "target": target,
        "expected_files": expected_files,
        "source_artifacts": [
            {"type": technical_spec.get("artifact_type"), "role": technical_spec.get("role")},
            {"type": implementation_plan.get("artifact_type"), "role": implementation_plan.get("role")},
            {"type": test_plan.get("artifact_type"), "role": test_plan.get("role")},
        ],
        "boundary": _boundary(implementation_plan, obligations),
        "nodes": nodes,
        "verifier_gates": gates,
        "programmer_handoff": {
            "next_role": "sandbox_programmer",
            "allowed_actions": ["synthesize_patch_in_sandbox", "run_verification", "emit_test_result"],
            "forbidden_actions": ["edit_source_project", "edit_registry", "skip_verifier_gates"],
        },
        "summary": {
            "node_count": len(nodes),
            "obligation_count": len(obligations),
            "gate_count": len(gates),
        },
    }


def _nodes(
    target: str,
    expected_files: list[str],
    contract: dict[str, Any],
    obligations: list[Any],
    gates: list[dict[str, str]],
) -> list[dict[str, Any]]:
    return [
        _node("T1", "bind_target", "implementation_target", "ready" if target else "needs_review", {"target": target}),
        _node("T2", "prepare_writable_scope", "sandbox_boundary", "ready" if expected_files else "needs_review", {"files": expected_files}),
        _node("T3", "map_contract_inputs", "implementation_contract", "ready", {"input_keys": sorted(contract)}),
        _node("T4", "materialize_acceptance", "tester_contract", "ready" if obligations else "needs_review", {"count": len(obligations)}),
        _node("T5", "verify_and_handoff", "reviewer_gate", "ready", {"required_gates": [gate["id"] for gate in gates]}),
    ]


def _node(node_id: str, action: str, owner: str, status: str, evidence: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": node_id,
        "action": action,
        "owner": owner,
        "status": status,
        "evidence": evidence,
        "source_code_changes_allowed": False,
    }


def _boundary(implementation_plan: dict[str, Any], obligations: list[Any]) -> dict[str, Any]:
    target = _target(implementation_plan)
    blocked = dict(implementation_plan.get("implementation_target") or {}).get("status") == "blocked_no_safe_candidate"
    return {
        "track": "blocked_handoff" if blocked else "sandbox_patch_tree",
        "target_bound": bool(target),
        "expected_file_count": len(_expected_files(implementation_plan)),
        "acceptance_obligation_count": len(obligations),
        "requires_dependency_profile": False,
        "requires_fixture_profile": False,
    }


def _verifier_gates(implementation_plan: dict[str, Any], obligations: list[Any]) -> list[dict[str, str]]:
    gates = [
        {"id": "sandbox_only", "status": "required"},
        {"id": "writable_scope_only", "status": "required"},
        {"id": "source_project_unchanged", "status": "required"},
    ]
    if obligations:
        gates.append({"id": "executable_acceptance", "status": "required"})
    if implementation_plan.get("verification_commands"):
        gates.append({"id": "allowed_verification_commands", "status": "required"})
    return gates


def _target(implementation_plan: dict[str, Any]) -> str:
    intent = dict(implementation_plan.get("patch_intent") or {})
    return str(intent.get("target_symbol") or dict(implementation_plan.get("implementation_target") or {}).get("candidate") or "")


def _expected_files(implementation_plan: dict[str, Any]) -> list[str]:
    files: list[str] = []
    for item in implementation_plan.get("expected_files", []):
        path = str(item).split(":", 1)[0]
        if path and path not in files:
            files.append(path)
    return files[:8]
