from __future__ import annotations

from typing import Any
from runtime.source_target_policy import implementation_policy_int, implementation_target_violation

def _greenfield_change_plan(
    technical_spec: dict[str, Any],
    target: dict[str, Any],
    expected_files: list[str],
) -> list[dict[str, Any]]:
    rows = [
        {
            "id": "CHANGE-001",
            "kind": "create_package_layout",
            "target": target.get("candidate"),
            "instruction": "Create isolated package files exactly within expected_files.",
        },
        {
            "id": "CHANGE-002",
            "kind": "implement_contracts",
            "target": "ProductTechnicalSpec.component_contracts",
            "instruction": "Implement component contracts as separate modules with typed dataclasses or explicit schemas.",
        },
        {
            "id": "CHANGE-003",
            "kind": "adapter_boundaries",
            "target": "ProductTechnicalSpec.external_boundaries",
            "instruction": "Keep network/filesystem/provider effects behind adapters and default tests fixture-only.",
        },
        {
            "id": "CHANGE-004",
            "kind": "verification_scaffold",
            "target": "tests/",
            "instruction": "Add fixture, contract, CLI and negative tests mapped to acceptance criteria.",
        },
        {
            "id": "CHANGE-005",
            "kind": "documentation",
            "target": "README.md",
            "instruction": "Document run commands, dependency policy, live-network policy, limitations and examples.",
        },
    ]
    for index, requirement in enumerate(list(technical_spec.get("requirements", []))[:6], start=6):
        rows.append(
            {
                "id": f"CHANGE-{index:03d}",
                "kind": "requirement_delta",
                "target": target.get("candidate"),
                "requirement_id": requirement.get("id"),
                "instruction": str(requirement.get("statement") or ""),
                "source": requirement.get("source"),
            }
        )
    if expected_files:
        rows.append(
            {
                "id": f"CHANGE-{len(rows) + 1:03d}",
                "kind": "scope_guard",
                "target": "expected_files",
                "instruction": "Reject implementation deltas outside expected_files unless SpecWriter updates ProductTechnicalSpec first.",
            }
        )
    return rows

def _greenfield_implementation_steps(technical_spec: dict[str, Any], target: dict[str, Any]) -> list[dict[str, Any]]:
    steps = [
        {
            "id": "IMPL-001",
            "action": f"Confirm ProductTechnicalSpec primary contract for {target.get('candidate')}.",
            "inputs": ["ProductTechnicalSpec.primary_contract"],
            "outputs": ["confirmed product implementation target"],
        },
        {
            "id": "IMPL-002",
            "action": "Create isolated package layout and do not modify user source tree.",
            "inputs": ["ImplementationPlan.expected_files"],
            "outputs": ["generated package skeleton"],
        },
        {
            "id": "IMPL-003",
            "action": "Implement CLI, core and adapters from component contracts before adding live integrations.",
            "inputs": ["ProductTechnicalSpec.component_contracts", "ProductTechnicalSpec.external_boundaries"],
            "outputs": ["component implementation units"],
        },
        {
            "id": "IMPL-004",
            "action": "Add fixture-first tests and negative tests before release review.",
            "inputs": ["ProductTechnicalSpec.acceptance_criteria", "ProductTechnicalSpec.verification_strategy"],
            "outputs": ["project-scoped verification evidence"],
        },
    ]
    for index, question in enumerate(list(technical_spec.get("open_questions", []))[:4], start=5):
        steps.append(
            {
                "id": f"IMPL-{index:03d}",
                "action": f"Carry open question into README/known limitations unless user clarifies: {question}",
                "inputs": ["ProductTechnicalSpec.open_questions"],
                "outputs": ["documented assumption or clarification request"],
            }
        )
    return steps

def _greenfield_quality_gates(technical_spec: dict[str, Any], expected_files: list[str]) -> list[dict[str, Any]]:
    acceptance = list(technical_spec.get("acceptance_criteria", []))
    return [
        {
            "id": "GATE-001",
            "name": "package_layout_within_scope",
            "check": "generated files are a subset of ImplementationPlan.expected_files",
            "expected_files": expected_files,
        },
        {
            "id": "GATE-002",
            "name": "component_contracts_implemented",
            "check": "each ProductTechnicalSpec component contract has an implementation unit",
            "component_count": len(list(technical_spec.get("component_contracts", []))),
        },
        {
            "id": "GATE-003",
            "name": "fixture_first_verification",
            "check": "default verification does not require live network or production credentials",
        },
        {
            "id": "GATE-004",
            "name": "acceptance_criteria_mapped",
            "check": "each ProductTechnicalSpec acceptance criterion has a test or review obligation",
            "acceptance_ids": [item.get("id") for item in acceptance[:12]],
        },
        {
            "id": "GATE-005",
            "name": "source_links_and_risks_preserved",
            "check": "reporting, adapter and risk requirements are preserved in README/tests",
        },
    ]

def _greenfield_package_contract(
    target: dict[str, Any],
    writable_scope: list[str],
    expected_files: list[str],
) -> dict[str, Any]:
    return {
        "artifact_type": "PatchPackage",
        "target": target.get("candidate"),
        "expected_files": expected_files,
        "allowed_write_scope": writable_scope,
        "required_sections": ["summary", "files", "verification", "known_limits", "run_instructions"],
        "apply_policy": "create isolated generated package first; direct user source apply is not applicable without explicit approval",
        "forbidden_paths": ["registry/capabilities.json", "artifacts/", ".git/"],
    }

def _greenfield_dependency_policy(technical_spec: dict[str, Any]) -> dict[str, Any]:
    constraints = " ".join(str(item).lower() for item in list(technical_spec.get("constraints", [])))
    security = " ".join(str(item).lower() for item in list(technical_spec.get("security_requirements", [])))
    external = " ".join(str(row).lower() for row in list(technical_spec.get("external_boundaries", [])))
    return {
        "new_runtime_dependencies": "stdlib_default_optional_adapters_require_explicit_spec",
        "pinning_required": True,
        "network_required_for_build": False,
        "live_network_default": "forbidden_in_tests",
        "live_network_allowed": "optional live network" in constraints or "network_optional" in external or "live" in security,
        "reason": "greenfield package must be runnable and testable without live services; optional adapters require explicit policy",
    }

def _expected_files(patch_scope: list[str]) -> list[str]:
    files = []
    for item in patch_scope:
        path = item.split(":", 1)[0]
        if path and path not in files:
            files.append(path)
    return files[:8]

def _implementation_evidence_scope(technical_spec: dict[str, Any], handoff: dict[str, Any]) -> list[str]:
    scope: list[str] = []
    for item in list(handoff.get("patch_scope") or []):
        _append_unique(scope, str(item))
    # Traceability rows are the reviewed requirement-to-source boundary. Keep
    # them ahead of the broader discovery evidence when the scope is capped.
    for row in list(technical_spec.get("traceability_table") or []):
        source = str(dict(row or {}).get("source") or "")
        if ":" in source:
            _append_unique(scope, source)
    for item in list(handoff.get("read_only_evidence_scope") or []):
        _append_unique(scope, str(item))
    for row in list(technical_spec.get("source_evidence") or []):
        source = str(dict(row or {}).get("source") or "")
        if ":" in source:
            _append_unique(scope, source)
    limit = max(1, implementation_policy_int("implementation_evidence_scope_limit", 8))
    return scope[:limit]

def _append_unique(rows: list[str], value: str) -> None:
    if value and value not in rows:
        rows.append(value)

def _bounded_patch_scope(evidence_scope: list[str], target: dict[str, Any]) -> list[str]:
    candidate = str(target.get("candidate") or "").strip()
    return [candidate] if candidate else []

def _writable_scope(target: dict[str, Any]) -> list[str]:
    candidate = str(target.get("candidate") or "").strip()
    return [candidate] if candidate else []

def _implementation_target(extraction_contract: dict[str, Any], patch_scope: list[str]) -> dict[str, Any]:
    if extraction_contract.get("status") == "blocked_no_safe_candidate":
        return {
            "candidate": None,
            "status": "blocked_no_safe_candidate",
            "source_contract": "TechnicalSpec.extraction_contract",
            "candidate_score": 0,
            "selection_reason": extraction_contract.get("selection_reason"),
        }
    candidate = str(extraction_contract.get("candidate") or (patch_scope[0] if patch_scope else ""))
    violation = implementation_target_violation(candidate)
    if violation.get("status") != "allowed":
        return {
            "candidate": None,
            "status": violation.get("status"),
            "source_contract": "TechnicalSpec.extraction_contract",
            "candidate_score": 0,
            "selection_reason": violation.get("selection_reason"),
            "rejected_candidate": candidate,
            "matched_policy_tokens": violation.get("matched_tokens", []),
            "blocked_by": violation.get("blocked_by", []),
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
        "contract_profile": extraction_contract.get("contract_profile", {}),
        "binding_status": _binding_status(extraction_contract, target),
    }

def _binding_status(extraction_contract: dict[str, Any], target: dict[str, Any]) -> str:
    if target.get("status") == "blocked_no_safe_candidate" or extraction_contract.get("status") == "blocked_no_safe_candidate":
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
                "action": _requirement_action(requirement, candidate),
                "inputs": [str(requirement.get("source"))],
                "outputs": ["implementation delta"],
            }
        )
    return steps

def _requirement_action(requirement: dict[str, Any], candidate: str) -> str:
    requirement_id = str(requirement.get("id") or "requirement")
    statement = str(requirement.get("statement") or "satisfy the TechnicalSpec requirement").strip()
    source = str(requirement.get("source") or "").strip()
    if source and source not in {"spec_writer_brief.scope", candidate}:
        return f"Satisfy {requirement_id} on {candidate}; treat {source} as read-only evidence context: {statement}"
    return f"Satisfy {requirement_id} on {candidate}: {statement}"

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
