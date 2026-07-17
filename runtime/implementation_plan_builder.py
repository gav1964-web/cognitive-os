"""Generic ImplementationPlan artifact builder."""

from __future__ import annotations

from typing import Any

from .role_implementer_blueprint import (
    build_executor_handoff,
    build_implementation_blueprint,
    build_patch_intent,
)
from .role_skill_common import now_iso


def build_implementation_plan(
    *,
    technical_spec: dict[str, Any],
    role_id: str = "implementer",
    next_role_id: str = "tester",
) -> dict[str, Any]:
    requirements = list(technical_spec.get("requirements", []))
    acceptance = list(technical_spec.get("acceptance_criteria", []))
    handoff = dict(technical_spec.get("implementation_handoff", {}))
    extraction_contract = dict(technical_spec.get("extraction_contract", {}))
    patch_scope = [str(item) for item in handoff.get("patch_scope", []) if item]
    target = _implementation_target(extraction_contract, patch_scope)
    writable_scope = _writable_scope(target)
    expected_files = _expected_files(writable_scope)
    binding = _contract_binding(extraction_contract, target)
    change_plan = _change_plan(requirements, patch_scope, target, binding)
    quality_gates = _quality_gates(expected_files, acceptance)
    verification_commands = _verification_commands()
    patch_intent = build_patch_intent(
        target=target,
        writable_scope=writable_scope,
        expected_files=expected_files,
        verification_commands=verification_commands,
    )
    return {
        "artifact_type": "ImplementationPlan",
        "role": role_id,
        "status": "ok",
        "created_at": now_iso(),
        "source_artifact": {
            "type": technical_spec.get("artifact_type"),
            "role": technical_spec.get("role"),
            "chosen_architecture_option": technical_spec.get("chosen_architecture_option"),
        },
        "implementation_target": target,
        "contract_binding": binding,
        "patch_scope": patch_scope,
        "evidence_scope": patch_scope,
        "writable_scope": writable_scope,
        "write_scope_policy": "Only writable_scope may be changed; patch_scope/evidence_scope is read-only context.",
        "expected_files": expected_files,
        "implementation_units": _implementation_units(target, binding, expected_files),
        "change_plan": change_plan,
        "implementation_blueprint": build_implementation_blueprint(
            target=target,
            binding=binding,
            change_plan=change_plan,
            quality_gates=quality_gates,
            acceptance=acceptance,
        ),
        "patch_intent": patch_intent,
        "executor_handoff": build_executor_handoff(patch_intent=patch_intent),
        "patch_package_contract": _patch_package_contract(target, writable_scope, expected_files),
        "dependency_policy": _dependency_policy(technical_spec),
        "implementation_steps": _implementation_steps(requirements, patch_scope, target),
        "quality_gates": quality_gates,
        "debug_rework_policy": _debug_rework_policy(),
        "verification_commands": verification_commands,
        "rollback_plan": _rollback_plan(expected_files),
        "acceptance_mapping": _acceptance_mapping(acceptance),
        "non_goals": technical_spec.get("non_goals", []),
        "forbidden_actions_observed": [],
        "forbidden_actions_enforced": ["write_code", "edit_registry", "execute_pipeline", "promote_candidate"],
        "next_artifact": {
            "type": "TestPlan",
            "recommended_role": next_role_id,
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


def _implementation_units(
    target: dict[str, Any],
    binding: dict[str, Any],
    expected_files: list[str],
) -> list[dict[str, Any]]:
    candidate = target.get("candidate")
    if not candidate:
        return []
    return [
        {
            "id": "UNIT-001",
            "target": candidate,
            "file": expected_files[0] if expected_files else str(candidate).split(":", 1)[0],
            "operation": "modify_existing_symbol_or_extract_adjacent_helper",
            "input_contract": binding.get("input_contract", {}),
            "output_contract": binding.get("output_contract", {}),
            "side_effect_policy": binding.get("side_effects", {}),
            "done_when": "target behavior satisfies mapped acceptance criteria without expanding writable_scope",
        }
    ]


def _change_plan(
    requirements: list[dict[str, Any]],
    patch_scope: list[str],
    target: dict[str, Any],
    binding: dict[str, Any],
) -> list[dict[str, Any]]:
    candidate = str(target.get("candidate") or "")
    if target.get("status") == "blocked_no_safe_candidate":
        return [
            {
                "id": "CHANGE-001",
                "kind": "stop",
                "target": "TechnicalSpec.extraction_contract",
                "instruction": "Do not generate a patch until a source-backed candidate exists.",
            }
        ]
    rows = [
        {
            "id": "CHANGE-001",
            "kind": "read_context",
            "target": candidate,
            "instruction": "Read candidate source, neighboring evidence_scope, and existing tests before editing.",
        },
        {
            "id": "CHANGE-002",
            "kind": "contract_shape",
            "target": candidate,
            "instruction": _contract_instruction(binding),
        },
        {
            "id": "CHANGE-003",
            "kind": "scope_guard",
            "target": candidate,
            "instruction": "Keep changed files inside writable_scope; use evidence_scope only to understand callers and side effects.",
        },
    ]
    for index, requirement in enumerate(requirements[:4], start=4):
        rows.append(
            {
                "id": f"CHANGE-{index:03d}",
                "kind": "requirement_delta",
                "target": candidate,
                "requirement_id": requirement.get("id"),
                "instruction": str(requirement.get("statement") or ""),
                "source": requirement.get("source"),
            }
        )
    if patch_scope:
        rows.append(
            {
                "id": f"CHANGE-{len(rows) + 1:03d}",
                "kind": "call_site_check",
                "target": candidate,
                "instruction": "Verify known callers still satisfy the input/output contract after the candidate change.",
            }
        )
    return rows


def _contract_instruction(binding: dict[str, Any]) -> str:
    inputs = ", ".join(f"{key}: {value}" for key, value in dict(binding.get("input_contract", {})).items())
    outputs = ", ".join(f"{key}: {value}" for key, value in dict(binding.get("output_contract", {})).items())
    return f"Preserve or introduce explicit boundary: input {{{inputs or 'payload: Any'}}}; output {{{outputs or 'result: Any'}}}."


def _patch_package_contract(
    target: dict[str, Any],
    writable_scope: list[str],
    expected_files: list[str],
) -> dict[str, Any]:
    return {
        "artifact_type": "PatchPackage",
        "target": target.get("candidate"),
        "expected_files": expected_files,
        "allowed_write_scope": writable_scope,
        "required_sections": ["summary", "patches", "verification", "rollback", "known_limits"],
        "apply_policy": "build isolated patch package first; direct source apply requires explicit human approval",
        "forbidden_paths": ["registry/capabilities.json", "artifacts/", ".git/"],
    }


def _dependency_policy(technical_spec: dict[str, Any]) -> dict[str, Any]:
    constraints = [str(item).lower() for item in technical_spec.get("constraints", [])]
    allow_new = any("dependency" in item and "allow" in item for item in constraints)
    return {
        "new_runtime_dependencies": "allowed_with_explicit_spec_constraint" if allow_new else "forbidden_by_default",
        "pinning_required": True,
        "network_required_for_build": False,
        "reason": "implementation must prefer existing project dependencies unless TechnicalSpec explicitly permits expansion",
    }


def _quality_gates(expected_files: list[str], acceptance: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "id": "GATE-001",
            "name": "changed_files_within_scope",
            "check": "changed files are a subset of ImplementationPlan.expected_files",
            "expected_files": expected_files,
        },
        {
            "id": "GATE-002",
            "name": "acceptance_criteria_mapped",
            "check": "each TechnicalSpec acceptance criterion has an implementation note or test obligation",
            "acceptance_ids": [item.get("id") for item in acceptance[:10]],
        },
        {
            "id": "GATE-003",
            "name": "no_registry_or_artifact_mutation",
            "check": "patch package does not mutate registry or generated evidence artifacts",
        },
    ]


def _debug_rework_policy() -> dict[str, Any]:
    return {
        "max_attempts": 2,
        "input_artifacts": ["TestResult", "ReviewFindings", "PatchPackage"],
        "failure_classes": ["contract_mismatch", "test_failure", "scope_violation", "dependency_error"],
        "output_artifact": "BoundedReworkPlan",
        "stop_conditions": [
            "same failure class repeats twice",
            "required change leaves writable_scope",
            "new dependency is needed but not allowed by TechnicalSpec",
        ],
    }


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

