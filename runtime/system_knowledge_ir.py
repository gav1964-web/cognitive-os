"""SystemKnowledgeIR v0 builders and validation helpers."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from runtime.system_knowledge_ir_inference import inferred_acceptance, inferred_behavior_contract


def build_system_knowledge_ir(
    *,
    project_report: dict[str, Any] | None = None,
    architecture_decision: dict[str, Any] | None = None,
    technical_spec: dict[str, Any] | None = None,
    implementation_plan: dict[str, Any] | None = None,
    test_plan: dict[str, Any] | None = None,
    origin: str = "role_artifacts",
) -> dict[str, Any]:
    """Build the common knowledge artifact used before source generation."""

    project_report = _content(project_report)
    architecture_decision = dict(architecture_decision or {})
    technical_spec = dict(technical_spec or {})
    implementation_plan = dict(implementation_plan or {})
    test_plan = dict(test_plan or {})
    summary = dict(project_report.get("summary", {}))
    scope = dict(dict(project_report.get("answers", {})).get("1_scope", {}))
    work_plan = dict(technical_spec.get("work_plan_contract", {}))
    first_slice = dict(architecture_decision.get("first_slice_contract", {}))
    interfaces = _interfaces(project_report, technical_spec)
    domain_model = _domain_model(project_report, summary, scope, technical_spec)
    ir = {
        "artifact_type": "SystemKnowledgeIR",
        "schema_version": "system_knowledge_ir.v0",
        "created_at": _now(),
        "origin": origin,
        "purpose": _purpose(summary, scope, architecture_decision, technical_spec),
        "project_identity": _project_identity(project_report, summary),
        "public_interfaces": interfaces,
        "domain_model": domain_model,
        "behavior_contracts": _behavior_contracts(technical_spec, interfaces, domain_model),
        "architecture_slices": _architecture_slices(architecture_decision, work_plan, first_slice),
        "dependency_policy": _dependency_policy(project_report, implementation_plan, technical_spec),
        "acceptance_tests": _acceptance_tests(technical_spec, test_plan, interfaces),
        "non_goals": _list_values(technical_spec.get("non_goals")),
        "source_traceability": _traceability(project_report, architecture_decision, technical_spec),
        "quality_targets": {
            "source_project_read_only": True,
            "line_limit": 400,
            "generated_project_can_compile": True,
            "round_trip_ir_diff_required": True,
        },
        "source_artifacts": _source_artifacts(
            project_report, architecture_decision, technical_spec, implementation_plan, test_plan
        ),
    }
    ir["verification"] = verify_system_knowledge_ir(ir)
    return ir


def build_system_knowledge_ir_from_dialogue(
    *,
    prompt: str,
    goal_spec: dict[str, Any] | None = None,
    constraints: list[str] | None = None,
    success_criteria: list[str] | None = None,
) -> dict[str, Any]:
    """Build a seed IR for prompt/dialogue-first systems."""

    goal_spec = dict(goal_spec or {})
    prompt_text = str(prompt or goal_spec.get("raw_prompt") or "").strip()
    ir = {
        "artifact_type": "SystemKnowledgeIR",
        "schema_version": "system_knowledge_ir.v0",
        "created_at": _now(),
        "origin": "dialogue",
        "purpose": goal_spec.get("intent") or prompt_text,
        "project_identity": {"name": goal_spec.get("target") or "dialogue_generated_system"},
        "public_interfaces": _dialogue_interfaces(goal_spec),
        "domain_model": {"entities": [], "data_artifacts": [], "open_questions": _open_questions(prompt_text)},
        "behavior_contracts": _dialogue_behavior_contracts(goal_spec, success_criteria),
        "architecture_slices": [],
        "dependency_policy": {"allowed": [], "constraints": _list_values(constraints or goal_spec.get("constraints"))},
        "acceptance_tests": _list_values(success_criteria or goal_spec.get("success_criteria")),
        "non_goals": _list_values(goal_spec.get("non_goals")),
        "source_traceability": [{"source": "dialogue.prompt", "claim": prompt_text[:240]}] if prompt_text else [],
        "quality_targets": {
            "source_project_read_only": True,
            "line_limit": 400,
            "generated_project_can_compile": True,
            "round_trip_ir_diff_required": True,
        },
        "source_artifacts": [{"artifact_type": "GoalSpec", "present": bool(goal_spec)}],
    }
    ir["verification"] = verify_system_knowledge_ir(ir)
    return ir


def verify_system_knowledge_ir(ir: dict[str, Any]) -> dict[str, Any]:
    required = [
        "artifact_type",
        "schema_version",
        "origin",
        "purpose",
        "project_identity",
        "public_interfaces",
        "behavior_contracts",
        "acceptance_tests",
        "source_traceability",
        "quality_targets",
    ]
    missing = [field for field in required if not ir.get(field)]
    warnings = []
    if not ir.get("architecture_slices"):
        warnings.append("architecture_slices_missing")
    if not ir.get("domain_model"):
        warnings.append("domain_model_missing")
    if not ir.get("acceptance_tests"):
        warnings.append("acceptance_tests_missing")
    score = round((len(required) - len(missing)) / len(required), 3)
    return {
        "status": "ok" if not missing else "needs_work",
        "score": score,
        "missing": missing,
        "warnings": warnings,
    }


def _content(value: dict[str, Any] | None) -> dict[str, Any]:
    payload = dict(value or {})
    return dict(payload.get("content", payload))


def _purpose(
    summary: dict[str, Any],
    scope: dict[str, Any],
    architecture_decision: dict[str, Any],
    technical_spec: dict[str, Any],
) -> str:
    for candidate in [
        scope.get("main_task"),
        architecture_decision.get("goal"),
        dict(technical_spec.get("source_artifact", {})).get("goal"),
        summary.get("description"),
        summary.get("project_type"),
    ]:
        text = str(candidate or "").strip()
        if text:
            return text
    return "Reproduce the observed system behavior from verified knowledge."


def _project_identity(project_report: dict[str, Any], summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "root": project_report.get("project") or summary.get("root"),
        "name": summary.get("name") or project_report.get("name") or "unknown_project",
        "frameworks": _list_values(summary.get("frameworks")),
        "entrypoints": _list_values(summary.get("entrypoints")),
    }


def _interfaces(project_report: dict[str, Any], technical_spec: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    summary = dict(project_report.get("summary", {}))
    for route in _route_values(summary.get("routes")):
        rows.append({"kind": "route", "name": route, "source": "ProjectMapReport.summary.routes"})
    for entrypoint in _list_values(summary.get("entrypoints")):
        rows.append({"kind": "entrypoint", "name": entrypoint, "source": "ProjectMapReport.summary.entrypoints"})
    for contract in technical_spec.get("interface_contracts", []) or []:
        if isinstance(contract, dict) and contract.get("source"):
            rows.append(
                {
                    "kind": "callable",
                    "name": contract.get("source"),
                    "input_contract": contract.get("input_contract", {}),
                    "output_contract": contract.get("output_contract", {}),
                    "source": "TechnicalSpec.interface_contracts",
                }
            )
    return _dedupe_named(rows)


def _domain_model(
    project_report: dict[str, Any],
    summary: dict[str, Any],
    scope: dict[str, Any],
    technical_spec: dict[str, Any],
) -> dict[str, Any]:
    domain_profile = dict(scope.get("domain_profile") or {})
    return {
        "project_type": summary.get("project_type") or summary.get("domain") or domain_profile.get("kind"),
        "frameworks": _list_values(summary.get("frameworks")),
        "data_artifacts": _list_values(project_report.get("data_artifacts")),
        "entities": _list_values(technical_spec.get("domain_entities")),
        "domain_profile": domain_profile,
    }


def _behavior_contracts(
    technical_spec: dict[str, Any],
    interfaces: list[dict[str, Any]],
    domain_model: dict[str, Any],
) -> list[dict[str, Any]]:
    rows = []
    extraction = dict(technical_spec.get("extraction_contract", {}))
    if extraction.get("candidate"):
        rows.append(
            {
                "source": extraction.get("candidate"),
                "contract_family": extraction.get("contract_family"),
                "input_contract": extraction.get("input_contract", {}),
                "output_contract": extraction.get("output_contract", {}),
                "failure_modes": _list_values(extraction.get("failure_modes")),
            }
        )
    for interface in interfaces:
        if interface.get("input_contract") or interface.get("output_contract"):
            rows.append(
                {
                    "source": interface.get("name"),
                    "input_contract": interface.get("input_contract", {}),
                    "output_contract": interface.get("output_contract", {}),
                }
            )
        elif interface.get("kind") in {"entrypoint", "route"}:
            rows.append(inferred_behavior_contract(interface, domain_model))
    return _dedupe_source(rows)


def _architecture_slices(
    architecture_decision: dict[str, Any],
    work_plan: dict[str, Any],
    first_slice: dict[str, Any],
) -> list[dict[str, Any]]:
    rows = []
    if first_slice:
        rows.append(
            {
                "id": first_slice.get("name") or first_slice.get("id") or "first_slice",
                "targets": _list_values(first_slice.get("targets")),
                "acceptance": _list_values(first_slice.get("acceptance_targets")),
                "source": "ArchitectureDecisionRecord.first_slice_contract",
            }
        )
    if work_plan:
        rows.append(
            {
                "id": work_plan.get("name") or "implementation_work_plan",
                "targets": _list_values(work_plan.get("targets")),
                "steps": _list_values(work_plan.get("steps")),
                "source": "TechnicalSpec.work_plan_contract",
            }
        )
    return rows


def _dependency_policy(
    project_report: dict[str, Any],
    implementation_plan: dict[str, Any],
    technical_spec: dict[str, Any],
) -> dict[str, Any]:
    summary = dict(project_report.get("summary", {}))
    return {
        "detected": _list_values(summary.get("dependencies")),
        "verification_commands": _list_values(implementation_plan.get("verification_commands")),
        "constraints": _list_values(technical_spec.get("constraints")),
    }


def _acceptance_tests(
    technical_spec: dict[str, Any],
    test_plan: dict[str, Any],
    interfaces: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows = []
    for item in technical_spec.get("acceptance_criteria", []) or []:
        if isinstance(item, dict):
            rows.append({"id": item.get("id"), "criterion": item.get("criterion"), "source": "TechnicalSpec"})
    for item in test_plan.get("acceptance_tests", []) or []:
        rows.append({"id": _field(item, "id"), "criterion": _field(item, "criterion", item), "source": "TestPlan"})
    if not rows:
        rows.extend(inferred_acceptance(interface) for interface in interfaces[:40])
    return rows


def _traceability(
    project_report: dict[str, Any],
    architecture_decision: dict[str, Any],
    technical_spec: dict[str, Any],
) -> list[dict[str, Any]]:
    rows = []
    for item in architecture_decision.get("traceability", []) or []:
        rows.append({"source": _field(item, "source"), "target": _field(item, "target"), "artifact": "ArchitectureDecisionRecord"})
    for item in technical_spec.get("traceability_table", []) or []:
        rows.append({"source": _field(item, "source"), "target": _field(item, "requirement"), "artifact": "TechnicalSpec"})
    if project_report.get("project"):
        rows.append({"source": project_report.get("project"), "target": "project_identity", "artifact": "ProjectMapReport"})
    return [row for row in rows if row.get("source") or row.get("target")]


def _source_artifacts(*artifacts: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {"artifact_type": artifact.get("artifact_type", "unknown"), "present": True}
        for artifact in artifacts
        if artifact
    ]


def _dialogue_interfaces(goal_spec: dict[str, Any]) -> list[dict[str, Any]]:
    outputs = _list_values(goal_spec.get("outputs"))
    return [{"kind": "declared_output", "name": item, "source": "GoalSpec.outputs"} for item in outputs]


def _dialogue_behavior_contracts(goal_spec: dict[str, Any], success_criteria: list[str] | None) -> list[dict[str, Any]]:
    inputs = _list_values(goal_spec.get("inputs"))
    outputs = _list_values(goal_spec.get("outputs"))
    criteria = _list_values(success_criteria or goal_spec.get("success_criteria"))
    if not inputs and not outputs and not criteria:
        return []
    return [{"source": "dialogue.goal", "inputs": inputs, "outputs": outputs, "acceptance": criteria}]


def _open_questions(prompt: str) -> list[str]:
    return ["Clarify public interfaces and acceptance tests."] if prompt else []


def _list_values(value: object) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return [item for item in value if item is not None and item != ""]
    if isinstance(value, tuple):
        return [item for item in value if item is not None and item != ""]
    if isinstance(value, set):
        return sorted(item for item in value if item is not None and item != "")
    if isinstance(value, dict):
        return [value]
    text = str(value).strip()
    return [text] if text else []


def _route_values(value: object) -> list[Any]:
    if isinstance(value, (int, float)):
        return []
    return _list_values(value)


def _field(value: object, name: str, fallback: object = None) -> Any:
    return value.get(name, fallback) if isinstance(value, dict) else fallback


def _dedupe_named(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen = set()
    result = []
    for row in rows:
        key = (row.get("kind"), row.get("name"))
        if key in seen or not row.get("name"):
            continue
        seen.add(key)
        result.append(row)
    return result


def _dedupe_source(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen = set()
    result = []
    for row in rows:
        key = str(row.get("source") or "")
        if key in seen or not key:
            continue
        seen.add(key)
        result.append(row)
    return result


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
