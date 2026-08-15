from __future__ import annotations

from typing import Any
from runtime.role_implementer_blueprint import (
    build_executor_handoff,
    build_implementation_blueprint,
    build_patch_intent,
)
from runtime.role_skill_common import now_iso
from runtime.stage2_template_routes import select_stage2_case
from runtime.greenfield_stage2_templates import expected_artifacts_for_case

def build_implementation_plan(
    *,
    technical_spec: dict[str, Any],
    role_id: str = "implementer",
    next_role_id: str = "tester",
) -> dict[str, Any]:
    if _is_greenfield_product_spec(technical_spec):
        return _build_greenfield_implementation_plan(
            technical_spec=technical_spec,
            role_id=role_id,
            next_role_id=next_role_id,
        )
    requirements = list(technical_spec.get("requirements", []))
    acceptance = list(technical_spec.get("acceptance_criteria", []))
    handoff = dict(technical_spec.get("implementation_handoff", {}))
    extraction_contract = dict(technical_spec.get("extraction_contract", {}))
    evidence_scope = _implementation_evidence_scope(technical_spec, handoff)
    target = _implementation_target(extraction_contract, evidence_scope)
    patch_scope = _bounded_patch_scope(evidence_scope, target)
    writable_scope = _writable_scope(target)
    expected_files = _expected_files(writable_scope)
    binding = _contract_binding(extraction_contract, target)
    change_plan = _change_plan(requirements, evidence_scope, target, binding)
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
        "evidence_scope": evidence_scope,
        "writable_scope": writable_scope,
        "write_scope_policy": "Only writable_scope may be changed; patch_scope is bounded planning scope and evidence_scope is read-only context.",
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
        "dependency_boundary_profile": dict(technical_spec.get("dependency_boundary_profile") or {}),
        "first_slice_reselection_request": dict(technical_spec.get("first_slice_reselection_request") or {}),
        "implementation_steps": _implementation_steps(requirements, evidence_scope, target),
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

def _build_greenfield_implementation_plan(
    *,
    technical_spec: dict[str, Any],
    role_id: str,
    next_role_id: str,
) -> dict[str, Any]:
    prompt = str(dict(technical_spec.get("source_artifact") or {}).get("prompt") or technical_spec.get("prompt") or "")
    case_name = select_stage2_case(prompt) or _case_from_primary_contract(technical_spec)
    expected_files = _greenfield_expected_files(case_name, technical_spec)
    target = {
        "candidate": f"greenfield:{case_name}",
        "source_contract": "ProductTechnicalSpec.primary_contract",
        "candidate_score": 100 if case_name != "generic_product" else 65,
        "selection_reason": "greenfield ProductTechnicalSpec maps to a supported Stage 2 package template",
        "mode": "greenfield_project",
        "case": case_name,
    }
    writable_scope = list(expected_files)
    patch_scope = list(expected_files)
    binding = _greenfield_contract_binding(technical_spec, target)
    change_plan = _greenfield_change_plan(technical_spec, target, expected_files)
    quality_gates = _greenfield_quality_gates(technical_spec, expected_files)
    verification_commands = ["python -m compileall -b .", "python -m pytest tests -q"]
    patch_intent = build_patch_intent(
        target=target,
        writable_scope=writable_scope,
        expected_files=expected_files,
        verification_commands=verification_commands,
    )
    blueprint = build_implementation_blueprint(
        target=target,
        binding=binding,
        change_plan=change_plan,
        quality_gates=quality_gates,
        acceptance=list(technical_spec.get("acceptance_criteria", [])),
    )
    blueprint["operation"] = "create_isolated_greenfield_package_from_product_spec"
    blueprint["project_case"] = case_name
    blueprint["component_to_file_map"] = _component_file_map(technical_spec, expected_files)
    blueprint["completion_signal"] = "VerifiedSystemPackage can be consumed by Tester/Reviewer without direct source apply."
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
        "evidence_scope": _greenfield_evidence_scope(technical_spec),
        "writable_scope": writable_scope,
        "write_scope_policy": "Create or modify only files listed in expected_files inside an isolated generated package.",
        "expected_files": expected_files,
        "implementation_units": _greenfield_implementation_units(technical_spec, expected_files),
        "change_plan": change_plan,
        "implementation_blueprint": blueprint,
        "patch_intent": patch_intent,
        "executor_handoff": build_executor_handoff(patch_intent=patch_intent),
        "patch_package_contract": _greenfield_package_contract(target, writable_scope, expected_files),
        "dependency_policy": _greenfield_dependency_policy(technical_spec),
        "implementation_steps": _greenfield_implementation_steps(technical_spec, target),
        "quality_gates": quality_gates,
        "debug_rework_policy": _debug_rework_policy(),
        "verification_commands": verification_commands,
        "rollback_plan": _rollback_plan(expected_files),
        "acceptance_mapping": _acceptance_mapping(list(technical_spec.get("acceptance_criteria", []))),
        "non_goals": technical_spec.get("non_goals", []),
        "greenfield_project_plan": {
            "case": case_name,
            "package_layout": expected_files,
            "component_to_file_map": _component_file_map(technical_spec, expected_files),
            "default_tests_are_fixture_only": True,
            "direct_user_source_modification": False,
        },
        "forbidden_actions_observed": [],
        "forbidden_actions_enforced": ["write_code", "edit_registry", "execute_pipeline", "promote_candidate"],
        "next_artifact": {
            "type": "TestPlan",
            "recommended_role": next_role_id,
            "reason": "greenfield implementation plan is ready for independent QA planning",
        },
    }

def _is_greenfield_product_spec(technical_spec: dict[str, Any]) -> bool:
    handoff = dict(technical_spec.get("implementation_handoff") or {})
    return technical_spec.get("artifact_type") == "ProductTechnicalSpec" or handoff.get("mode") == "greenfield_project"

def _case_from_primary_contract(technical_spec: dict[str, Any]) -> str:
    primary = dict(technical_spec.get("primary_contract") or {})
    name = str(primary.get("name") or "").lower()
    if "webresearchrequest" in name or "researchreport" in name:
        return "web_research_summarizer_cli"
    return "generic_product"

def _greenfield_expected_files(case_name: str, technical_spec: dict[str, Any]) -> list[str]:
    configured = expected_artifacts_for_case(case_name, str(dict(technical_spec.get("source_artifact") or {}).get("prompt") or ""))
    if configured:
        return configured
    package = case_name.replace("-", "_")
    components = [str(row.get("component") or row.get("id") or "") for row in list(technical_spec.get("component_contracts", [])) if isinstance(row, dict)]
    files = ["pyproject.toml", "README.md", f"src/{package}/__init__.py", f"src/{package}/cli.py"]
    for component in components:
        if component and component not in {"cli_boundary", "interface", "api_boundary"}:
            files.append(f"src/{package}/{component}.py")
    files.append("tests/test_cli.py")
    files.append("tests/test_core.py")
    return list(dict.fromkeys(files))

def _greenfield_contract_binding(technical_spec: dict[str, Any], target: dict[str, Any]) -> dict[str, Any]:
    primary = dict(technical_spec.get("primary_contract") or {})
    return {
        "candidate": target.get("candidate"),
        "input_contract": {"request": primary.get("input") or "Product request"},
        "output_contract": {"result": primary.get("output") or "Product result"},
        "side_effects": {"policy": primary.get("side_effect_policy") or "adapter-only"},
        "evidence_source": "ProductTechnicalSpec.primary_contract",
        "binding_status": "bound_to_product_contract",
    }

def _greenfield_evidence_scope(technical_spec: dict[str, Any]) -> list[str]:
    return [
        "ProductTechnicalSpec.primary_contract",
        "ProductTechnicalSpec.component_contracts",
        "ProductTechnicalSpec.acceptance_criteria",
        "ProductTechnicalSpec.verification_strategy",
        "ProductTechnicalSpec.error_model",
    ]

def _greenfield_implementation_units(technical_spec: dict[str, Any], expected_files: list[str]) -> list[dict[str, Any]]:
    file_map = _component_file_map(technical_spec, expected_files)
    rows = []
    for index, contract in enumerate(list(technical_spec.get("component_contracts", [])), start=1):
        if not isinstance(contract, dict):
            continue
        component = str(contract.get("component") or f"component_{index}")
        rows.append(
            {
                "id": f"UNIT-{index:03d}",
                "target": component,
                "file": file_map.get(component, expected_files[min(index, len(expected_files) - 1)] if expected_files else ""),
                "operation": "create_component_module_or_adapter",
                "input_contract": contract.get("input_contract", []),
                "output_contract": contract.get("output_contract", []),
                "side_effect_policy": _side_effect_policy_for_component(technical_spec, component),
                "done_when": "component satisfies ProductTechnicalSpec contract and has fixture/negative test coverage",
            }
        )
    return rows

def _component_file_map(technical_spec: dict[str, Any], expected_files: list[str]) -> dict[str, str]:
    normalized = {path.replace("\\", "/").lower(): path for path in expected_files}
    mapping: dict[str, str] = {}
    component_names = [
        str(row.get("component") or "")
        for row in list(technical_spec.get("component_contracts", []))
        if isinstance(row, dict) and row.get("component")
    ]
    for component in component_names:
        tokens = _component_tokens(component)
        match = next((original for lowered, original in normalized.items() if any(token in lowered for token in tokens)), None)
        if match is None and "cli" in component:
            match = next((original for lowered, original in normalized.items() if lowered.endswith("/cli.py")), None)
        mapping[component] = match or (expected_files[0] if expected_files else "")
    return mapping

def _component_tokens(component: str) -> list[str]:
    lowered = component.lower()
    tokens = [lowered, lowered.replace("_adapter", ""), lowered.replace("_boundary", ""), lowered.replace("_core", "")]
    if "search" in lowered:
        tokens.append("search")
    if "fetch" in lowered:
        tokens.append("fetcher")
    if "extract" in lowered:
        tokens.append("extractor")
    if "summar" in lowered:
        tokens.append("summarizer")
    if "report" in lowered or "serial" in lowered:
        tokens.append("report")
    return list(dict.fromkeys(token for token in tokens if token))

def _side_effect_policy_for_component(technical_spec: dict[str, Any], component: str) -> dict[str, Any]:
    for boundary in list(technical_spec.get("external_boundaries", [])):
        if isinstance(boundary, dict) and str(boundary.get("target") or "") == component:
            return {
                "side_effects": list(boundary.get("side_effects", [])),
                "policy": boundary.get("policy"),
            }
    return {"side_effects": [], "policy": "pure or project-local operation unless listed in external_boundaries"}
