from __future__ import annotations

from typing import Any

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
                "instruction": "Do not generate a patch until a writable runtime candidate exists.",
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
        "python -m compileall .",
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
            "criterion": _expanded_acceptance_criterion(item),
            "verification": _expanded_acceptance_verification(item),
        }
        for item in acceptance[:10]
    ]

def _expanded_acceptance_criterion(item: dict[str, Any]) -> str:
    criterion = str(item.get("criterion") or "").strip()
    if len(criterion) >= 24:
        return criterion
    return f"Implementer must provide explicit code and test evidence for acceptance criterion: {criterion}."

def _expanded_acceptance_verification(item: dict[str, Any]) -> str:
    verification = str(item.get("verification") or "").strip()
    criterion = str(item.get("criterion") or "").strip()
    if len(verification) >= 24 and criterion.lower() in verification.lower():
        return verification
    return f"{verification or 'pytest or review'} must verify `{criterion}` with a concrete fixture, assertion, or review checklist item."
