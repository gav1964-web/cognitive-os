from __future__ import annotations

from typing import Any
from runtime.python_source_files import is_python_source_ref


def _subsystem_boundaries(project_report: dict[str, Any], tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summary = dict(project_report.get("summary", {}))
    answers = dict(project_report.get("answers", {}))
    readiness = dict(answers.get("6_runtime_extraction_readiness", {}))
    execution = dict(answers.get("2_execution", {}))
    entrypoints = _dedupe_strings(
        [str(item) for item in list(summary.get("entrypoints", [])) + list(execution.get("entrypoints", [])) if item]
        + _node_refs(execution.get("central_flow_nodes", []))
        + _plan_capability_refs(readiness)
    )[:5]
    boundaries = [
        {
            "id": "runtime_entrypoints",
            "purpose": "Own user-facing execution entrypoints, inferred flow anchors, and request intake.",
            "owned_files": entrypoints or ["ProjectMapReport.execution_anchor_missing"],
            "inputs": ["CLI arguments", "HTTP requests", "scheduled events"],
            "outputs": ["runtime call into core logic", "user-visible response"],
        }
    ]
    targets = _targets_by_type(tasks, {"MAP_SUBSYSTEM_BOUNDARY", "CLARIFY_OWNERSHIP_BOUNDARY"})
    for target in targets[:4]:
        boundaries.append(
            {
                "id": _safe_id(target),
                "purpose": f"Clarify ownership and dependencies around {target}.",
                "owned_files": [target],
                "inputs": ["typed data from callers"],
                "outputs": ["typed data or explicit side effect"],
            }
        )
    for orchestrator in list(readiness.get("hidden_orchestrators", []))[:4]:
        if not isinstance(orchestrator, dict):
            continue
        target = f"{orchestrator.get('path')}:{orchestrator.get('name')}"
        boundaries.append(
            {
                "id": _safe_id(target),
                "purpose": f"Own hidden orchestration and runtime decisions around {target}.",
                "owned_files": [target],
                "inputs": ["typed data or runtime request from upstream step"],
                "outputs": ["downstream capability calls, typed data, or explicit side effect"],
            }
        )
    return boundaries

def _capability_model(plan: dict[str, Any], tasks: list[dict[str, Any]], first_slice: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for target in list(first_slice.get("targets", []))[:8]:
        rows.append(
            {
                "source": target,
                "reason": first_slice.get("goal") or "ProjectArchitectureSynthesis recommended first bounded slice.",
                "status": "first_slice_candidate",
                "next_step": "write TechnicalSpec work_plan_contract and acceptance checks",
                "slice": first_slice.get("name"),
            }
        )
    for item in list(plan.get("capabilities_to_extract", []))[:12]:
        rows.append(
            {
                "source": item.get("capability"),
                "reason": item.get("why"),
                "status": "candidate",
                "next_step": "write TechnicalSpec before Foundry build",
            }
        )
    for task in tasks:
        if task.get("type") in {"EXTRACT_CAPABILITY", "DRAFT_PIPELINE_CAPABILITY"}:
            rows.append(
                {
                    "source": task.get("target"),
                    "reason": task.get("title"),
                    "status": "candidate",
                    "next_step": "derive input/output contract",
                }
            )
    return _dedupe_by(rows, "source")[:12]

def _risks(project_report: dict[str, Any], tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    risks = []
    report_risks = project_report.get("risks", [])
    if isinstance(report_risks, list):
        for item in report_risks[:5]:
            risks.append(
                _risk_record(
                    source="ProjectMapReport.risks",
                    severity="medium",
                    description=str(item),
                    mitigation="carry this risk into TechnicalSpec acceptance or explicitly mark it out of first-slice scope",
                    category="project_report_risk",
                )
            )
    for task in tasks:
        if task.get("priority") == "P1":
            risks.append(
                _risk_record(
                    source=str(task.get("task_id") or task.get("target") or "analysis_task"),
                    severity="high",
                    description=str(task.get("title") or "High-priority architecture task requires mitigation."),
                    mitigation=str(task.get("acceptance") or "must be addressed or explicitly accepted before promotion"),
                    category=str(task.get("type") or "analysis_task"),
                    target=task.get("target"),
                )
            )
    if not risks:
        risks.append(
            _risk_record(
                source="architect",
                severity="low",
                description="No high-priority risks detected in ProjectMapReport; keep first slice bounded until evidence changes.",
                mitigation="preserve no-source-mutation policy and verify selected contract before implementation",
                category="residual_risk",
            )
        )
    return risks[:8]

def _risk_record(
    *,
    source: str,
    severity: str,
    description: str,
    mitigation: str,
    category: str,
    target: object | None = None,
) -> dict[str, Any]:
    return {
        "source": source,
        "severity": severity,
        "category": category,
        "description": description,
        "impact": _risk_impact(severity, category),
        "mitigation": mitigation,
        "evidence_source": source,
        "target": target,
        "owner_role": "architect",
        "acceptance_gate": "TechnicalSpec acceptance or explicit risk acceptance before promotion",
    }

def _risk_impact(severity: str, category: str) -> str:
    if severity == "high":
        return f"{category} can make the first slice unsafe, unreplayable, or too broad for implementation handoff"
    if severity == "medium":
        return f"{category} can reduce confidence in contracts or verification scope"
    return "residual risk is acceptable only while the first slice remains bounded and source-backed"

def _data_lifecycle(readiness: dict[str, Any]) -> list[dict[str, Any]]:
    rows = readiness.get("data_lifecycle", [])
    if isinstance(rows, list) and rows:
        return [
            {
                "stage": row.get("stage"),
                "shape": row.get("shape"),
                "evidence": row.get("evidence"),
            }
            for row in rows[:8]
            if isinstance(row, dict)
        ]
    return [
        {"stage": "input", "shape": "project-specific request or file payload", "evidence": "ProjectMapReport scope"},
        {"stage": "processing", "shape": "typed function arguments or intermediate artifacts", "evidence": "ProjectMapReport execution"},
        {"stage": "output", "shape": "explicit return value, file, response, or side effect", "evidence": "ProjectMapReport outputs"},
    ]

def _state_model(readiness: dict[str, Any], project_report: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in list(readiness.get("long_lived_state", []))[:8]:
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "owner": item.get("target") or item.get("source") or item.get("kind"),
                "kind": item.get("kind"),
                "lifetime": "longer_than_single_call",
                "checkpoint_policy": "record before retry/replay or mark as non-reusable",
            }
        )
    answers = dict(project_report.get("answers", {}))
    preserve = dict(answers.get("5_errors_state_repro", {})).get("state_to_preserve", [])
    for item in list(preserve)[:6]:
        rows.append(
            {
                "owner": str(item),
                "kind": "reproducibility_state",
                "lifetime": "scenario_replay",
                "checkpoint_policy": "persist with run id, code version, and config snapshot",
            }
        )
    return _dedupe_by(rows, "owner") or [
        {
            "owner": "execution_inputs",
            "kind": "reproducibility_state",
            "lifetime": "scenario_replay",
            "checkpoint_policy": "persist input, config, code version, and final report",
        }
    ]

def _external_boundaries(readiness: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in list(readiness.get("process_boundary_candidates", []))[:8]:
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "target": item.get("target") or f"{item.get('path')}:{item.get('name')}",
                "reasons": item.get("reasons", []),
                "policy": "isolate behind process or adapter boundary before retry/replay",
            }
        )
    for item in list(readiness.get("quarantine_candidates", []))[:8]:
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "target": item.get("target"),
                "reasons": item.get("reasons", []),
                "policy": "quarantine on dependency drift or repeated runtime failure",
            }
        )
    return _dedupe_by(rows, "target")

def _quality_attributes(readiness: dict[str, Any], risks: list[dict[str, Any]]) -> list[dict[str, str]]:
    attributes = [
        {
            "name": "traceability",
            "requirement": "Every architectural recommendation must link to ProjectMapReport evidence.",
        },
        {
            "name": "replay_safety",
            "requirement": "Side-effecting steps need idempotency or checkpoint policy before automated retry.",
        },
        {
            "name": "bounded_change",
            "requirement": "First implementation handoff must target one source-backed capability candidate.",
        },
    ]
    if readiness.get("process_boundary_candidates"):
        attributes.append(
            {
                "name": "failure_isolation",
                "requirement": "Network, subprocess, filesystem, or database-heavy operations must have an isolation boundary.",
            }
        )
    if any(risk.get("severity") == "high" for risk in risks):
        attributes.append(
            {
                "name": "risk_acceptance",
                "requirement": "High-priority risks require mitigation or explicit acceptance before promotion.",
            }
        )
    return attributes

def _contract_targets(files_or_symbols: list[str], source_context: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for source in files_or_symbols[:16]:
        if not _implementation_source(source):
            continue
        context = dict(source_context.get(source, {}))
        signature = dict(context.get("signature", {}))
        rows.append(
            {
                "source": source,
                "input_hint": signature.get("args") or ["derive from source signature or caller context"],
                "output_hint": signature.get("returns") or "derive from return paths and tests",
                "side_effects": context.get("side_effects", []),
            }
        )
    return rows

def _implementation_source(source: str) -> bool:
    if is_python_source_ref(source) and ":" in source:
        return True
    lowered = source.lower()
    if lowered.startswith("[") and " " in lowered:
        return True
    return False

def _open_questions(project_report: dict[str, Any], tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    questions = [
        {"source": task.get("task_id"), "question": task.get("title")}
        for task in tasks
        if task.get("type") in {"ANSWER_OPEN_QUESTION", "REVIEW_HUMAN_DECISION"}
    ]
    if questions:
        return questions[:5]
    answers = dict(project_report.get("answers", {}))
    if not answers:
        return [{"source": "architect", "question": "Project report has no structured answers; confirm project scope."}]
    return []
