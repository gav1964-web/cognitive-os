"""Implementer planner role skill."""

from __future__ import annotations

from typing import Any

from .role_skill_common import now_iso


def run_implementer_skill(*, technical_spec: dict[str, Any]) -> dict[str, Any]:
    requirements = list(technical_spec.get("requirements", []))
    acceptance = list(technical_spec.get("acceptance_criteria", []))
    handoff = dict(technical_spec.get("implementation_handoff", {}))
    extraction_contract = dict(technical_spec.get("extraction_contract", {}))
    patch_scope = [str(item) for item in handoff.get("patch_scope", []) if item]
    target = _implementation_target(extraction_contract, patch_scope)
    writable_scope = _writable_scope(target)
    expected_files = _expected_files(writable_scope)
    return {
        "artifact_type": "ImplementationPlan",
        "role": "implementer",
        "status": "ok",
        "created_at": now_iso(),
        "source_artifact": {
            "type": technical_spec.get("artifact_type"),
            "role": technical_spec.get("role"),
            "chosen_architecture_option": technical_spec.get("chosen_architecture_option"),
        },
        "implementation_target": target,
        "contract_binding": _contract_binding(extraction_contract, target),
        "patch_scope": patch_scope,
        "evidence_scope": patch_scope,
        "writable_scope": writable_scope,
        "write_scope_policy": "Only writable_scope may be changed; patch_scope/evidence_scope is read-only context.",
        "expected_files": expected_files,
        "implementation_steps": _implementation_steps(requirements, patch_scope, target),
        "verification_commands": _verification_commands(),
        "rollback_plan": _rollback_plan(expected_files),
        "acceptance_mapping": _acceptance_mapping(acceptance),
        "non_goals": technical_spec.get("non_goals", []),
        "forbidden_actions_observed": [],
        "forbidden_actions_enforced": ["write_code", "edit_registry", "execute_pipeline", "promote_candidate"],
        "next_artifact": {
            "type": "TestPlan",
            "recommended_role": "tester",
            "reason": "implementation plan is ready for independent QA planning",
        },
    }


def _expected_files(patch_scope: list[str]) -> list[str]:
    files = []
    for item in patch_scope:
        path = item.split(":", 1)[0]
        if path and path not in files:
            files.append(path)
    return files[:8]


def _writable_scope(target: dict[str, Any]) -> list[str]:
    candidate = str(target.get("candidate") or "").strip()
    return [candidate] if candidate else []


def _implementation_target(extraction_contract: dict[str, Any], patch_scope: list[str]) -> dict[str, Any]:
    candidate = str(extraction_contract.get("candidate") or (patch_scope[0] if patch_scope else ""))
    if not candidate and extraction_contract.get("status") == "blocked_no_safe_candidate":
        return {
            "candidate": None,
            "status": "blocked_no_safe_candidate",
            "source_contract": "TechnicalSpec.extraction_contract",
            "candidate_score": 0,
            "selection_reason": extraction_contract.get("selection_reason"),
        }
    return {
        "candidate": candidate,
        "source_contract": "TechnicalSpec.extraction_contract" if extraction_contract else "TechnicalSpec.patch_scope",
        "candidate_score": extraction_contract.get("candidate_score"),
        "selection_reason": extraction_contract.get("selection_reason"),
    }


def _contract_binding(extraction_contract: dict[str, Any], target: dict[str, Any]) -> dict[str, Any]:
    return {
        "candidate": target.get("candidate"),
        "input_contract": extraction_contract.get("input_contract", {"payload": "Any"}),
        "output_contract": extraction_contract.get("output_contract", {"result": "Any"}),
        "side_effects": extraction_contract.get("side_effects", {}),
        "evidence_source": extraction_contract.get("evidence_source"),
        "binding_status": _binding_status(extraction_contract),
    }


def _binding_status(extraction_contract: dict[str, Any]) -> str:
    if extraction_contract.get("status") == "blocked_no_safe_candidate":
        return "blocked_no_safe_candidate"
    return "bound_to_extraction_contract" if extraction_contract.get("candidate") else "fallback_to_patch_scope"


def _implementation_steps(
    requirements: list[dict[str, Any]],
    patch_scope: list[str],
    target: dict[str, Any],
) -> list[dict[str, Any]]:
    candidate = str(target.get("candidate") or "selected candidate")
    if target.get("status") == "blocked_no_safe_candidate":
        return [
            {
                "id": "IMPL-001",
                "action": "Stop implementation planning until source-specific extraction evidence exists.",
                "inputs": ["TechnicalSpec.extraction_contract"],
                "outputs": ["blocked implementation handoff"],
            },
            {
                "id": "IMPL-002",
                "action": "Ask Project Analyzer or ArchitectSkill to identify a bounded candidate before any code change.",
                "inputs": ["ProjectMapReport", "ArchitectureDecisionRecord"],
                "outputs": ["rework request for source evidence"],
            },
        ]
    steps = [
        {
            "id": "IMPL-001",
            "action": f"Review TechnicalSpec extraction contract for {candidate}.",
            "inputs": ["TechnicalSpec.extraction_contract"],
            "outputs": ["confirmed implementation target"],
        },
        {
            "id": "IMPL-002",
            "action": f"Prepare candidate changes for {candidate} only inside writable_scope.",
            "inputs": patch_scope or ["TechnicalSpec.patch_scope"],
            "outputs": ["patch draft or Foundry candidate update"],
        },
    ]
    for index, requirement in enumerate(requirements[:4], start=3):
        steps.append(
            {
                "id": f"IMPL-{index:03d}",
                "action": f"Satisfy {requirement.get('id')}: {requirement.get('statement')}",
                "inputs": [str(requirement.get("source"))],
                "outputs": ["implementation delta"],
            }
        )
    return steps


def _verification_commands() -> list[str]:
    return [
        "python -m pytest -q",
        "python -m compileall runtime tools plugins",
        "python tools/mvp_acceptance.py --root . --skip-pytest",
    ]


def _rollback_plan(expected_files: list[str]) -> dict[str, Any]:
    return {
        "strategy": "revert only files touched by this implementation plan",
        "files": expected_files,
        "registry_policy": "do not edit registry except explicit Foundry promote",
        "artifact_policy": "keep role artifacts for audit unless explicitly cleaned",
    }


def _acceptance_mapping(acceptance: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "acceptance_id": item.get("id"),
            "criterion": item.get("criterion"),
            "verification": item.get("verification"),
        }
        for item in acceptance[:10]
    ]
