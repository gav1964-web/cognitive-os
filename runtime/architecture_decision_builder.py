"""Generic ArchitectureDecisionRecord artifact builder."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from .local_inference import LocalInferenceConfig
from .role_architect_llm import apply_architect_advisory
from .role_skill_common import now_iso
from .role_source_context import build_source_context


def build_architecture_decision(
    *,
    goal: str,
    project_report: dict[str, Any],
    role_id: str = "architect",
    next_role_id: str = "spec_writer",
    constraints: list[str] | None = None,
    advisory_config: LocalInferenceConfig | None = None,
) -> dict[str, Any]:
    summary = dict(project_report.get("summary", {}))
    answers = dict(project_report.get("answers", {}))
    readiness = dict(answers.get("6_runtime_extraction_readiness", {}))
    plan = dict(readiness.get("minimal_extraction_plan", {}))
    tasks = _tasks(project_report)
    synthesis = _architecture_synthesis(project_report)
    first_slice = _first_slice_contract(synthesis)
    boundaries = _subsystem_boundaries(project_report, tasks)
    capabilities = _capability_model(plan, tasks, first_slice)
    risks = _risks(project_report, tasks)
    open_questions = _open_questions(project_report, tasks)
    data_lifecycle = _data_lifecycle(readiness)
    state_model = _state_model(readiness, project_report)
    external_boundaries = _external_boundaries(readiness)
    options = _architecture_options(capabilities, risks, open_questions)
    chosen = _chosen_option(options)
    rejected = [item for item in options if item["id"] != chosen["id"]]
    traceability = _traceability(tasks, capabilities, risks, first_slice)
    context_sources = _context_sources(capabilities, risks, traceability) + _important_runtime_sources(project_report)
    source_context = build_source_context(
        project_root=str(summary.get("root") or project_report.get("root") or ""),
        project_report=project_report,
        sources=_dedupe_strings(context_sources)[:36],
    )
    artifact = {
        "artifact_type": "ArchitectureDecisionRecord",
        "role": role_id,
        "status": "ok",
        "created_at": now_iso(),
        "goal": goal,
        "project": summary.get("root") or project_report.get("root"),
        "decision_summary": _decision_summary(summary, capabilities, risks),
        "source_strata": _source_strata(readiness),
        "subsystem_boundaries": boundaries,
        "data_lifecycle": data_lifecycle,
        "state_model": state_model,
        "external_boundaries": external_boundaries,
        "quality_attributes": _quality_attributes(readiness, risks),
        "capability_model": capabilities,
        "architecture_synthesis": _architecture_synthesis_summary(synthesis),
        "first_slice_contract": first_slice,
        "risks": risks,
        "non_goals": _non_goals(),
        "open_questions": open_questions,
        "traceability": traceability,
        "source_context": source_context,
        "architecture_options": options,
        "chosen_option": chosen,
        "rejected_options": _rejected_options(rejected),
        "spec_writer_brief": _spec_writer_brief(
            chosen,
            capabilities,
            risks,
            traceability,
            source_context,
            data_lifecycle=data_lifecycle,
            state_model=state_model,
            external_boundaries=external_boundaries,
            first_slice=first_slice,
        ),
        "constraints": constraints or [],
        "next_artifact": {
            "type": "TechnicalSpec",
            "recommended_role": next_role_id,
            "reason": "architecture decision is ready for acceptance criteria and traceability mapping",
        },
        "forbidden_actions_observed": [],
        "forbidden_actions_enforced": ["write_code", "edit_registry", "execute_pipeline", "promote_candidate"],
    }
    return apply_architect_advisory(artifact, config=advisory_config)


def _architecture_options(
    capabilities: list[dict[str, Any]],
    risks: list[dict[str, Any]],
    open_questions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    high_risk = any(risk.get("severity") == "high" for risk in risks)
    has_questions = bool(open_questions)
    return [
        {
            "id": "minimal_safe_extraction",
            "title": "Extract the safest focused capability first.",
            "tradeoffs": ["fast feedback", "small blast radius", "limited architecture cleanup"],
            "prerequisites": ["TechnicalSpec with input/output contract", "Foundry dry-run promotion"],
            "risk_score": 1 if capabilities else 4,
            "fit_score": 9 if capabilities else 4,
        },
        {
            "id": "contract_hardening_first",
            "title": "Harden weak contracts before extraction.",
            "tradeoffs": ["better future stability", "slower first capability delivery"],
            "prerequisites": ["Identify boundary schemas", "Add negative contract tests"],
            "risk_score": 2 if high_risk else 3,
            "fit_score": 8 if high_risk or has_questions else 5,
        },
        {
            "id": "full_subsystem_split",
            "title": "Split subsystems before capability extraction.",
            "tradeoffs": ["clean target architecture", "largest scope and highest drift risk"],
            "prerequisites": ["Owned subsystem map", "Migration plan", "Regression safety net"],
            "risk_score": 7,
            "fit_score": 3,
        },
    ]


def _chosen_option(options: list[dict[str, Any]]) -> dict[str, Any]:
    selected = sorted(options, key=lambda item: (_option_score(item), item["id"]), reverse=True)[0]
    return {
        "id": selected["id"],
        "title": selected["title"],
        "reason": (
            f"highest fit-to-risk score ({_option_score(selected)}) for a bounded first transformation step; "
            f"fit={selected.get('fit_score')}, risk={selected.get('risk_score')}"
        ),
        "tradeoffs": selected["tradeoffs"],
        "prerequisites": selected["prerequisites"],
        "fit_score": selected.get("fit_score"),
        "risk_score": selected.get("risk_score"),
        "decision_score": _option_score(selected),
    }


def _rejected_options(options: list[dict[str, Any]]) -> list[dict[str, Any]]:
    best_score = max((_option_score(item) for item in options), default=0)
    return [
        {
            "id": item["id"],
            "title": item["title"],
            "reason_rejected": _rejection_reason(item, best_score),
            "tradeoffs": item.get("tradeoffs", []),
            "prerequisites": item.get("prerequisites", []),
            "fit_score": item.get("fit_score"),
            "risk_score": item.get("risk_score"),
            "decision_score": _option_score(item),
            "score_delta": best_score - _option_score(item),
            "deferred_until": _deferred_until(item),
        }
        for item in options
    ]


def _option_score(option: dict[str, Any]) -> int:
    return int(option.get("fit_score") or 0) - int(option.get("risk_score") or 0)


def _rejection_reason(option: dict[str, Any], best_score: int) -> str:
    score = _option_score(option)
    tradeoffs = ", ".join(str(item) for item in list(option.get("tradeoffs", []))[:2])
    return (
        f"deferred because decision_score={score} is {best_score - score} below selected option; "
        f"tradeoffs considered: {tradeoffs or 'not specified'}"
    )


def _deferred_until(option: dict[str, Any]) -> str:
    option_id = str(option.get("id") or "")
    if option_id == "full_subsystem_split":
        return "after first extracted capability has contract tests, replay evidence, and stable ownership map"
    if option_id == "contract_hardening_first":
        return "after high-risk weak contracts block the selected first slice or negative tests expose drift"
    return "after selected first slice fails acceptance or risk assumptions change"


def _spec_writer_brief(
    chosen: dict[str, Any],
    capabilities: list[dict[str, Any]],
    risks: list[dict[str, Any]],
    traceability: list[dict[str, Any]],
    source_context: dict[str, dict[str, Any]],
    *,
    data_lifecycle: list[dict[str, Any]],
    state_model: list[dict[str, Any]],
    external_boundaries: list[dict[str, Any]],
    first_slice: dict[str, Any],
) -> dict[str, Any]:
    files_or_symbols = _brief_sources(capabilities, source_context, traceability)
    contract_targets = _contract_targets(files_or_symbols, source_context)
    if not files_or_symbols:
        return {
            "scope": [chosen.get("title"), "Stop before implementation because no source-specific capability candidate is available."],
            "files_or_symbols": [],
            "acceptance_targets": ["Project Analyzer reports no safe Python extraction candidate; SpecWriter must preserve a blocked handoff."],
            "constraints": ["no source rewrite in architecture phase", "do not invent extraction targets without source evidence"],
            "risk_focus": [risk.get("description") for risk in risks[:4]],
            "data_lifecycle": data_lifecycle,
            "state_model": state_model,
            "external_boundaries": external_boundaries,
            "first_slice": first_slice,
            "contract_targets": [],
            "blocked_by": ["no_safe_source_specific_candidate"],
        }
    return {
        "scope": [chosen.get("title"), "Prepare one implementable capability extraction spec."],
        "files_or_symbols": files_or_symbols,
        "acceptance_targets": [row.get("acceptance") or row.get("requirement") for row in traceability[:6]],
        "constraints": ["no source rewrite in architecture phase", "Foundry gates required before promotion"],
        "risk_focus": [risk.get("description") for risk in risks[:4]],
        "data_lifecycle": data_lifecycle,
        "state_model": state_model,
        "external_boundaries": external_boundaries,
        "first_slice": first_slice,
        "contract_targets": contract_targets,
    }


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
    lowered = source.lower()
    if ".py:" in lowered:
        return True
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


def _traceability(
    tasks: list[dict[str, Any]],
    capabilities: list[dict[str, Any]],
    risks: list[dict[str, Any]],
    first_slice: dict[str, Any],
) -> list[dict[str, Any]]:
    rows = []
    for index, step in enumerate(list(first_slice.get("steps", []))[:8], start=1):
        targets = list(first_slice.get("targets", []))
        rows.append(
            {
                "source": "ProjectArchitectureSynthesis.recommended_first_slice",
                "requirement": str(step),
                "target": targets[min(index - 1, len(targets) - 1)] if targets else first_slice.get("name"),
                "acceptance": f"First slice `{first_slice.get('name')}` records and verifies step {index}: {step}",
            }
        )
    for task in tasks[:8]:
        rows.append(
            {
                "source": task.get("task_id"),
                "requirement": task.get("title"),
                "target": task.get("target"),
                "acceptance": task.get("acceptance"),
            }
        )
    for item in capabilities[:16]:
        rows.append({"source": item.get("source"), "requirement": "Capability candidate requires TechnicalSpec."})
    for risk in risks[:4]:
        rows.append({"source": risk.get("source"), "requirement": "Risk must be addressed or accepted before promotion."})
    return rows


def _architecture_synthesis(project_report: dict[str, Any]) -> dict[str, Any]:
    synthesis = project_report.get("architecture_synthesis")
    if isinstance(synthesis, dict):
        return synthesis
    content = project_report.get("content")
    if isinstance(content, dict) and isinstance(content.get("architecture_synthesis"), dict):
        return dict(content["architecture_synthesis"])
    return _fallback_architecture_synthesis(project_report)


def _fallback_architecture_synthesis(project_report: dict[str, Any]) -> dict[str, Any]:
    summary = dict(project_report.get("summary", {}))
    answers = dict(project_report.get("answers", {}))
    readiness = dict(answers.get("6_runtime_extraction_readiness", {}))
    plan = dict(readiness.get("minimal_extraction_plan", {}))
    candidates = [
        str(row.get("capability"))
        for row in list(plan.get("capabilities_to_extract", []) or [])
        if isinstance(row, dict) and row.get("capability")
    ]
    if not candidates:
        return {}
    entrypoints = [str(item) for item in list(summary.get("entrypoints", []) or []) if item]
    dataflows = [
        str(row.get("entrypoint"))
        for row in list(readiness.get("dataflows", []) or [])
        if isinstance(row, dict) and row.get("entrypoint")
    ]
    primary = candidates[0]
    return {
        "artifact_type": "ProjectArchitectureSynthesis",
        "source": "ArchitectureDecisionRecord.fallback_from_project_map_report",
        "synthesis_id": "fallback_project_map_report",
        "confidence": 0.72,
        "project_profile": {
            "archetype": _fallback_project_archetype(summary, readiness),
            "entrypoints": entrypoints[:6],
            "languages": list(summary.get("languages", []) or [])[:6],
            "evidence": _dedupe_strings(entrypoints + dataflows + candidates)[:12],
        },
        "project_diagnosis": (
            "ProjectMapReport has runtime extraction facts but no explicit architecture_synthesis; "
            "ADR builds a conservative first slice from source-backed capability candidates."
        ),
        "target_architecture_shape": [
            "Keep entrypoint/orchestration code outside the first writable scope.",
            "Extract one source-backed capability contract before broader refactoring.",
            "Carry filesystem/network side effects behind explicit validation gates.",
        ],
        "recommended_first_slice": {
            "name": _fallback_slice_name(primary),
            "goal": str(plan.get("goal") or "Extract the first source-backed reusable capability."),
            "targets": candidates[:8],
            "steps": _fallback_slice_steps(primary, plan, readiness),
            "knowledge_rule": "project_map_report_minimal_extraction_plan",
        },
    }


def _fallback_project_archetype(summary: dict[str, Any], readiness: dict[str, Any]) -> str:
    frameworks = {str(item).lower() for item in list(summary.get("frameworks", []) or [])}
    entrypoints = " ".join(str(item).lower() for item in list(summary.get("entrypoints", []) or []))
    dataflows = list(readiness.get("dataflows", []) or [])
    if any(item in frameworks for item in {"fastapi", "flask", "django"}) or "api" in entrypoints:
        return "python_service"
    if dataflows or any(item.endswith(".py") for item in list(summary.get("entrypoints", []) or [])):
        return "python_cli_or_file_pipeline"
    return "python_project"


def _fallback_slice_name(primary: str) -> str:
    name = primary.rsplit(":", 1)[-1].strip() or "first_capability"
    return f"first_slice_{_safe_id(name)}"


def _fallback_slice_steps(primary: str, plan: dict[str, Any], readiness: dict[str, Any]) -> list[str]:
    side_effects = [str(item) for item in list(plan.get("side_effects_to_isolate", []) or []) if item]
    return [
        f"Confirm `{primary}` has a stable input/output contract from source evidence.",
        f"Keep writable scope limited to `{primary}` until TechnicalSpec acceptance passes.",
        "Map caller and callee context before implementation handoff.",
        "Add contract tests for the selected capability before promotion.",
        *(f"Isolate side-effecting target `{target}` outside the first pure contract." for target in side_effects[:3]),
    ]


def _first_slice_contract(synthesis: dict[str, Any]) -> dict[str, Any]:
    first_slice = dict(synthesis.get("recommended_first_slice") or {})
    targets = _dedupe_strings([str(item) for item in list(first_slice.get("targets", [])) if item])
    steps = _dedupe_strings([str(item) for item in list(first_slice.get("steps", [])) if item])
    if not first_slice and not targets and not steps:
        return {}
    return {
        "name": str(first_slice.get("name") or "first_bounded_capability_slice"),
        "goal": str(first_slice.get("goal") or "Define the first bounded capability transformation."),
        "targets": targets[:8],
        "steps": steps[:12],
        "knowledge_rule": first_slice.get("knowledge_rule"),
        "selection_policy": "choose the smallest source-backed slice that can produce a TechnicalSpec without widening writable scope",
        "handoff_expectation": "SpecWriter may reject or rerank weak targets, but must preserve this slice as evidence",
        "deferred_targets": targets[8:16],
        "source_artifact": synthesis.get("artifact_type") or "ProjectArchitectureSynthesis",
        "source": "ProjectArchitectureSynthesis.recommended_first_slice",
    }


def _architecture_synthesis_summary(synthesis: dict[str, Any]) -> dict[str, Any]:
    if not synthesis:
        return {}
    return {
        "artifact_type": synthesis.get("artifact_type"),
        "source": synthesis.get("source"),
        "synthesis_id": synthesis.get("synthesis_id"),
        "confidence": synthesis.get("confidence"),
        "project_profile": synthesis.get("project_profile", {}),
        "project_diagnosis": synthesis.get("project_diagnosis"),
        "target_architecture_shape": list(synthesis.get("target_architecture_shape", []))[:8],
    }


def _context_sources(
    capabilities: list[dict[str, Any]],
    risks: list[dict[str, Any]],
    traceability: list[dict[str, Any]],
) -> list[str]:
    values = [
        *(item.get("source") for item in capabilities),
        *(item.get("source") for item in risks),
        *(item.get("source") for item in traceability),
        *(item.get("target") for item in traceability),
    ]
    return [str(value) for value in values if value]


def _important_runtime_sources(project_report: dict[str, Any]) -> list[str]:
    summary = dict(project_report.get("summary", {}))
    answers = dict(project_report.get("answers", {}))
    capabilities = dict(answers.get("3_capabilities", {}))
    readiness = dict(answers.get("6_runtime_extraction_readiness", {}))
    rows: list[str] = []
    for key in (
        "hidden_orchestrators",
        "mixed_responsibility_functions",
        "process_boundary_candidates",
        "idempotency_risks",
    ):
        for item in readiness.get(key, [])[:12]:
            if not isinstance(item, dict):
                continue
            target = item.get("target") or (
                f"{item.get('path')}:{item.get('name')}" if item.get("path") and item.get("name") else ""
            )
            if target:
                rows.append(str(target))
    for item in capabilities.get("pure_transforms", [])[:40]:
        if not isinstance(item, dict):
            continue
        target = f"{item.get('path')}:{item.get('name')}" if item.get("path") and item.get("name") else ""
        if target and _domain_evidence_source(target):
            rows.append(target)
    root = Path(str(summary.get("root") or project_report.get("root") or ""))
    rows.extend(_provider_parser_sources(root))
    return rows


def _provider_parser_sources(project_root: Path) -> list[str]:
    if not project_root.exists() or not project_root.is_dir():
        return []
    rows: list[str] = []
    markers = ("normalize", "parse", "extract", "curl_fallback", "fetch_available_models")
    for path in list(project_root.rglob("*_llm_client.py"))[:20]:
        try:
            module = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
        except (OSError, SyntaxError):
            continue
        relative = path.relative_to(project_root).as_posix()
        for node in module.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            name = node.name
            if any(marker in name.lower() for marker in markers):
                rows.append(f"{relative}:{name}")
    return rows[:24]


def _brief_sources(
    capabilities: list[dict[str, Any]],
    source_context: dict[str, dict[str, Any]],
    traceability: list[dict[str, Any]],
) -> list[str]:
    neighbor_sources: list[str] = []
    for item in source_context.values():
        neighbor_sources.extend(str(row) for row in item.get("callees", []) if row)
    candidates = _dedupe_strings(
        [str(item.get("source")) for item in capabilities if item.get("source")]
        + [str(item.get("source")) for item in traceability if item.get("source")]
        + list(source_context)
        + neighbor_sources
    )
    return sorted(
        [source for source in candidates if _implementation_brief_source(source)],
        key=lambda source: (0 if source in source_context else 1, *_brief_source_sort_key(source)),
    )[:32]


def _implementation_brief_source(source: str) -> bool:
    lowered = "/" + source.replace("\\", "/").lower().lstrip("/")
    if ".py:" not in lowered:
        return False
    return not any(
        token in lowered
        for token in (
            "/.github/",
            "/bench/",
            "/benchmarks/",
            "/doc/",
            "/docs/",
            "/examples/",
            "/scripts/",
            "/tasks/",
            "/test/",
            "/tests/",
            "/testing/",
            "/tools/",
            "/__pycache__/",
        )
    )


def _domain_evidence_source(source: str) -> bool:
    lowered = source.lower()
    return any(
        token in lowered
        for token in (
            "_llm_client.py:",
            "download_ready_map.py:",
            "import_indoc.py:",
            "app.py:incident_features",
            "app.py:features_for_view",
            "app.py:calculate_data_bounds",
            "providers/factory.py:",
            "handlers_openai.py:",
            "complexity_router.py:",
        )
    )


def _brief_source_sort_key(source: str) -> tuple[int, str]:
    lowered = source.lower()
    score = 0
    if any(token in lowered for token in ("service.py:", "providers/factory.py", "import_indoc.py:parse_file")):
        score -= 40
    if any(token in lowered for token in ("parse", "resolve", "build_providers", "features_for_view", "incident_features", "rtf_to_text")):
        score -= 20
    if any(token in lowered for token in ("download_ready_map.py:download_file",)):
        score -= 14
    if any(token in lowered for token in ("_llm_client.py:", "handlers_openai.py", "complexity_router.py", "_start_local_llm_process")):
        score -= 12
    if any(token in lowered for token in ("api.py:describe_module", "_plugin_metadata.py", "downloader.py:worker")):
        score += 25
    if "p0042/api.py:describe_module" in lowered:
        score -= 40
    if any(token in lowered for token in ("debug_", "_print_", "_prompt_hints.py", "_prompt_intent.py")):
        score += 35
    if any(token in lowered for token in ("tests/", "docs/", "examples/", "scratch/")):
        score += 40
    return (score, source)


def _tasks(project_report: dict[str, Any]) -> list[dict[str, Any]]:
    tasks = dict(project_report.get("analysis_tasks", {})).get("tasks", [])
    return [item for item in tasks if isinstance(item, dict)]


def _targets_by_type(tasks: list[dict[str, Any]], types: set[str]) -> list[str]:
    return [str(task.get("target")) for task in tasks if task.get("type") in types and task.get("target")]


def _node_refs(rows: object) -> list[str]:
    if not isinstance(rows, list):
        return []
    refs = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        if row.get("path") and row.get("name"):
            refs.append(f"{row.get('path')}:{row.get('name')}")
    return refs


def _plan_capability_refs(readiness: dict[str, Any]) -> list[str]:
    plan = dict(readiness.get("minimal_extraction_plan", {}))
    rows = plan.get("capabilities_to_extract", [])
    if not isinstance(rows, list):
        return []
    return [str(row.get("capability")) for row in rows if isinstance(row, dict) and row.get("capability")]


def _decision_summary(summary: dict[str, Any], capabilities: list[dict[str, Any]], risks: list[dict[str, Any]]) -> str:
    project = summary.get("root", "project")
    return f"Treat {project} as a candidate for bounded capability extraction: {len(capabilities)} capability candidates, {len(risks)} architecture risks."


def _source_strata(readiness: dict[str, Any]) -> dict[str, Any]:
    strata = readiness.get("source_strata", {})
    if not isinstance(strata, dict):
        return {}
    return {
        "active_core": list(strata.get("active_core", []))[:24],
        "legacy_noise": list(strata.get("legacy_noise", []))[:24],
        "context_only": list(strata.get("context_only", []))[:24],
        "packaged_copy": list(strata.get("packaged_copy", []))[:24],
        "policy": "Use active_core for first extraction candidates; keep legacy_noise/context_only as evidence, not first targets.",
    }


def _non_goals() -> list[str]:
    return [
        "Do not rewrite the whole project in the first transformation step.",
        "Do not mutate Capability Registry from ArchitectSkill.",
        "Do not promote generated candidates without Foundry dry-run and explicit approval.",
        "Do not replace deterministic runtime validation with role output.",
    ]


def _dedupe_by(rows: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    result = []
    seen = set()
    for row in rows:
        value = row.get(key)
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(row)
    return result


def _dedupe_strings(values: list[str]) -> list[str]:
    result = []
    seen = set()
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _safe_id(value: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "_" for ch in value).strip("_")[:60] or "boundary"

