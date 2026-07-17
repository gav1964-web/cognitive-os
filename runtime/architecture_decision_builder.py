"""Generic ArchitectureDecisionRecord artifact builder."""

from __future__ import annotations

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
    boundaries = _subsystem_boundaries(project_report, tasks)
    capabilities = _capability_model(plan, tasks)
    risks = _risks(project_report, tasks)
    open_questions = _open_questions(project_report, tasks)
    options = _architecture_options(capabilities, risks, open_questions)
    chosen = _chosen_option(options)
    rejected = [item for item in options if item["id"] != chosen["id"]]
    traceability = _traceability(tasks, capabilities, risks)
    source_context = build_source_context(
        project_root=str(summary.get("root") or project_report.get("root") or ""),
        project_report=project_report,
        sources=_context_sources(capabilities, risks, traceability),
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
        "capability_model": capabilities,
        "risks": risks,
        "non_goals": _non_goals(),
        "open_questions": open_questions,
        "traceability": traceability,
        "source_context": source_context,
        "architecture_options": options,
        "chosen_option": chosen,
        "rejected_options": _rejected_options(rejected),
        "spec_writer_brief": _spec_writer_brief(chosen, capabilities, risks, traceability),
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
    selected = sorted(options, key=lambda item: (int(item["fit_score"]) - int(item["risk_score"]), item["id"]), reverse=True)[0]
    return {
        "id": selected["id"],
        "title": selected["title"],
        "reason": "highest fit-to-risk score for a bounded first transformation step",
        "tradeoffs": selected["tradeoffs"],
        "prerequisites": selected["prerequisites"],
    }


def _rejected_options(options: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {"id": item["id"], "title": item["title"], "reason_rejected": "lower fit-to-risk score for the current MVP step"}
        for item in options
    ]


def _spec_writer_brief(
    chosen: dict[str, Any],
    capabilities: list[dict[str, Any]],
    risks: list[dict[str, Any]],
    traceability: list[dict[str, Any]],
) -> dict[str, Any]:
    files_or_symbols = [str(item.get("source")) for item in capabilities[:6] if item.get("source")]
    if not files_or_symbols:
        return {
            "scope": [chosen.get("title"), "Stop before implementation because no source-specific capability candidate is available."],
            "files_or_symbols": [],
            "acceptance_targets": ["Project Analyzer reports no safe Python extraction candidate; SpecWriter must preserve a blocked handoff."],
            "constraints": ["no source rewrite in architecture phase", "do not invent extraction targets without source evidence"],
            "risk_focus": [risk.get("description") for risk in risks[:4]],
            "blocked_by": ["no_safe_source_specific_candidate"],
        }
    return {
        "scope": [chosen.get("title"), "Prepare one implementable capability extraction spec."],
        "files_or_symbols": files_or_symbols,
        "acceptance_targets": [row.get("acceptance") or row.get("requirement") for row in traceability[:6]],
        "constraints": ["no source rewrite in architecture phase", "Foundry gates required before promotion"],
        "risk_focus": [risk.get("description") for risk in risks[:4]],
    }


def _subsystem_boundaries(project_report: dict[str, Any], tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summary = dict(project_report.get("summary", {}))
    answers = dict(project_report.get("answers", {}))
    readiness = dict(answers.get("6_runtime_extraction_readiness", {}))
    entrypoints = list(summary.get("entrypoints", []))[:5]
    boundaries = [
        {
            "id": "runtime_entrypoints",
            "purpose": "Own user-facing execution entrypoints and request intake.",
            "owned_files": entrypoints,
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


def _capability_model(plan: dict[str, Any], tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for item in list(plan.get("capabilities_to_extract", []))[:6]:
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
    return _dedupe_by(rows, "source")[:8]


def _risks(project_report: dict[str, Any], tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    risks = []
    report_risks = project_report.get("risks", [])
    if isinstance(report_risks, list):
        for item in report_risks[:5]:
            risks.append({"source": "ProjectMapReport.risks", "severity": "medium", "description": str(item)})
    for task in tasks:
        if task.get("priority") == "P1":
            risks.append(
                {
                    "source": task.get("task_id"),
                    "severity": "high",
                    "description": task.get("title"),
                    "mitigation": task.get("acceptance"),
                }
            )
    if not risks:
        risks.append({"source": "architect", "severity": "low", "description": "No high-priority risks detected."})
    return risks[:8]


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
) -> list[dict[str, Any]]:
    rows = []
    for task in tasks[:8]:
        rows.append(
            {
                "source": task.get("task_id"),
                "requirement": task.get("title"),
                "target": task.get("target"),
                "acceptance": task.get("acceptance"),
            }
        )
    for item in capabilities[:6]:
        rows.append({"source": item.get("source"), "requirement": "Capability candidate requires TechnicalSpec."})
    for risk in risks[:4]:
        rows.append({"source": risk.get("source"), "requirement": "Risk must be addressed or accepted before promotion."})
    return rows


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


def _tasks(project_report: dict[str, Any]) -> list[dict[str, Any]]:
    tasks = dict(project_report.get("analysis_tasks", {})).get("tasks", [])
    return [item for item in tasks if isinstance(item, dict)]


def _targets_by_type(tasks: list[dict[str, Any]], types: set[str]) -> list[str]:
    return [str(task.get("target")) for task in tasks if task.get("type") in types and task.get("target")]


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


def _safe_id(value: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "_" for ch in value).strip("_")[:60] or "boundary"

