"""Greenfield product TechnicalSpec builder."""

from __future__ import annotations

from typing import Any

from .role_skill_common import now_iso


def build_product_technical_spec(architecture: dict[str, Any], *, role_id: str = "spec_writer") -> dict[str, Any]:
    brief = dict(architecture.get("spec_writer_brief", {}))
    primary = dict(brief.get("primary_contract", {}))
    components = list(architecture.get("components", []))
    return {
        "artifact_type": "ProductTechnicalSpec",
        "role": role_id,
        "status": "ok" if architecture.get("status") == "ok" else "blocked",
        "created_at": now_iso(),
        "source_artifact": {
            "type": architecture.get("artifact_type"),
            "role": architecture.get("role"),
            "prompt": architecture.get("prompt"),
        },
        "scope": list(brief.get("scope", [])),
        "requirements": _requirements(architecture, primary),
        "component_contracts": _component_contracts(components),
        "primary_contract": primary,
        "interfaces": list(architecture.get("interfaces", [])),
        "product_output_contract": dict(brief.get("product_output_contract") or architecture.get("product_output_contract") or {}),
        "real_world_edge_cases": list(brief.get("real_world_edge_cases") or architecture.get("real_world_edge_cases") or []),
        "data_model": list(architecture.get("data_model", [])),
        "data_lifecycle": list(architecture.get("data_lifecycle", [])),
        "research_hints": list(architecture.get("research_hints", [])),
        "architecture_options": list(architecture.get("architecture_options", [])),
        "chosen_architecture_option": architecture.get("chosen_architecture_option"),
        "security_requirements": list(architecture.get("security_policy", [])),
        "state_and_replay_policy": list(architecture.get("state_and_replay_policy", [])),
        "error_model": _error_model(architecture),
        "acceptance_criteria": _acceptance(architecture),
        "verification_strategy": _verification_strategy(architecture),
        "implementation_handoff": {
            "recommended_role": "implementer",
            "expected_output": "ImplementationPlan",
            "mode": "greenfield_project",
            "components": [str(row.get("id")) for row in components if isinstance(row, dict)],
            "must_not_start_with": ["direct subprocess control", "secret logging", "production deployment"],
        },
        "constraints": list(brief.get("constraints", [])),
        "non_goals": list(architecture.get("non_goals", [])),
        "open_questions": list(architecture.get("open_questions", [])),
        "forbidden_actions_observed": [],
        "forbidden_actions_enforced": ["write_code", "edit_registry", "execute_pipeline", "promote_candidate"],
    }


def _requirements(architecture: dict[str, Any], primary: dict[str, Any]) -> list[dict[str, str]]:
    rows = []
    for item in list(dict(architecture.get("spec_writer_brief", {})).get("scope", [])):
        rows.append(
            {
                "id": f"REQ-{len(rows) + 1:03d}",
                "priority": "MUST",
                "statement": str(item),
                "source": "ProductArchitectureRecord.scope",
            }
        )
    rows.append(
        {
            "id": f"REQ-{len(rows) + 1:03d}",
            "priority": "MUST",
            "statement": f"Primary contract {primary.get('name')} must define input, output, error and side-effect policy.",
            "source": "ProductArchitectureRecord.primary_contract",
        }
    )
    for risk in list(architecture.get("risks", []))[:8]:
        rows.append(
            {
                "id": f"REQ-{len(rows) + 1:03d}",
                "priority": "MUST" if risk.get("severity") == "high" else "SHOULD",
                "statement": f"Risk {risk.get('risk')} must be mitigated: {risk.get('mitigation')}",
                "source": "ProductArchitectureRecord.risks",
            }
        )
    return rows


def _component_contracts(components: list[Any]) -> list[dict[str, Any]]:
    rows = []
    for row in components:
        if not isinstance(row, dict):
            continue
        rows.append(
            {
                "component": row.get("id"),
                "purpose": row.get("purpose"),
                "input_contract": list(row.get("inputs", [])),
                "output_contract": list(row.get("outputs", [])),
            }
        )
    return rows


def _error_model(architecture: dict[str, Any]) -> list[dict[str, str]]:
    rows = [
        {"error": "bad_input", "handling": "reject request with typed ErrorResponse before side effects", "source": "api_boundary"},
        {"error": "contract_mismatch", "handling": "stop handoff and return to SpecWriter/Architect", "source": "primary_contract"},
    ]
    for boundary in list(architecture.get("external_boundaries", [])):
        rows.append(
            {
                "error": "external_boundary_failure",
                "handling": f"isolate/quarantine {boundary.get('target')} and return typed failure",
                "source": str(boundary.get("target")),
            }
        )
    return rows


def _acceptance(architecture: dict[str, Any]) -> list[dict[str, str]]:
    focus = list(dict(architecture.get("spec_writer_brief", {})).get("acceptance_focus", []))
    rows = [
        {"id": f"AC-{index + 1:03d}", "criterion": str(item), "verification": _acceptance_verification(str(item))}
        for index, item in enumerate(focus)
    ]
    rows.append(
        {
            "id": f"AC-{len(rows) + 1:03d}",
            "criterion": "README contains local run, test and dependency policy.",
            "verification": "documentation review",
        }
    )
    return rows


def _acceptance_verification(criterion: str) -> str:
    lowered = criterion.lower()
    if any(marker in lowered for marker in ("contract", "schema", "request", "response", "output", "summary", "source")):
        return "contract test checks the stated input/output shape and source traceability"
    if any(marker in lowered for marker in ("negative", "invalid", "failure", "timeout", "malformed", "empty", "cyrillic", "rotated")):
        return "negative pytest fixture covers the named failure or edge condition"
    if any(marker in lowered for marker in ("fixture", "without network", "no live", "fake", "mock")):
        return "fixture-only pytest run proves behavior without live external services"
    if any(marker in lowered for marker in ("dependency", "backend", "adapter")):
        return "dependency/backend policy review plus adapter-boundary test"
    if any(marker in lowered for marker in ("readme", "run", "documentation")):
        return "documentation review verifies exact local run and test commands"
    return "pytest or explicit review checklist tied to this criterion"


def _verification_strategy(architecture: dict[str, Any]) -> dict[str, Any]:
    focus = [str(item) for item in list(dict(architecture.get("spec_writer_brief", {})).get("acceptance_focus", []))]
    edges = [str(row.get("id") or row.get("description")) for row in architecture.get("real_world_edge_cases", []) if isinstance(row, dict)]
    contract_tests = ["validate request schemas", "verify primary contract output shape"]
    negative_tests = ["invalid input", "adapter failure", "secret redaction"]
    for item in focus:
        lowered = item.lower()
        if any(marker in lowered for marker in ("output", "summary", "source", "contract", "top-15", "plain query")):
            contract_tests.append(item)
        if any(marker in lowered for marker in ("cyrillic", "empty", "malformed", "noisy", "timeout", "failure")):
            negative_tests.append(item)
    return {
        "contract_tests": _dedupe(contract_tests),
        "negative_tests": _dedupe(negative_tests),
        "integration_tests": ["run with fake adapters only", "no live external service required for default tests"],
        "real_world_scenarios": edges,
        "manual_review": list(architecture.get("open_questions", [])),
    }


def _dedupe(values: list[str]) -> list[str]:
    result = []
    seen = set()
    for value in values:
        key = value.strip().lower()
        if key and key not in seen:
            result.append(value)
            seen.add(key)
    return result
