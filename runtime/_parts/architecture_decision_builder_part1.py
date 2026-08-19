from __future__ import annotations

import ast
from pathlib import Path
from typing import Any
from runtime.architecture_decision_policy import load_architecture_decision_policy, policy_list, policy_rules
from runtime.architecture_slice_naming import semantic_first_slice_name
from runtime.local_inference import LocalInferenceConfig
from runtime.role_architect_llm import apply_architect_advisory
from runtime.role_skill_common import now_iso
from runtime.role_source_context import build_source_context

ARCHITECTURE_DECISION_POLICY = load_architecture_decision_policy()
FALLBACK_ARCHETYPE_POLICY = dict(ARCHITECTURE_DECISION_POLICY["fallback_archetype"])
FALLBACK_SLICE_POLICY = dict(ARCHITECTURE_DECISION_POLICY["fallback_slice"])
SOURCE_SELECTION_POLICY = dict(ARCHITECTURE_DECISION_POLICY["source_selection"])
CONTEXT_ONLY_PATH_TOKENS = policy_list(SOURCE_SELECTION_POLICY, "context_only_path_tokens")
DOMAIN_EVIDENCE_SOURCE_TOKENS = policy_list(SOURCE_SELECTION_POLICY, "domain_evidence_source_tokens")
PROVIDER_PARSER_FILE_GLOBS = policy_list(SOURCE_SELECTION_POLICY, "provider_parser_file_globs")
PROVIDER_PARSER_FUNCTION_MARKERS = policy_list(SOURCE_SELECTION_POLICY, "provider_parser_function_markers")
FALLBACK_READ_FILE_PATH_TOKENS = policy_list(SOURCE_SELECTION_POLICY, "fallback_read_file_path_tokens")
CALLABLE_TRANSFORM_FALLBACK_POLICY = dict(SOURCE_SELECTION_POLICY.get("callable_transform_fallback") or {})
BRIEF_SORT_RULES = policy_rules(SOURCE_SELECTION_POLICY, "brief_sort_rules")

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
    first_slice = _first_slice_with_source_targets(first_slice, tasks, plan=plan)
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
        function_scoped_dependencies=True,
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
        "fact_judgment_ledger": _fact_judgment_ledger(
            summary=summary,
            boundaries=boundaries,
            capabilities=capabilities,
            risks=risks,
            first_slice=first_slice,
        ),
        "spec_writer_handoff_readiness": _spec_writer_handoff_readiness(
            capabilities=capabilities,
            traceability=traceability,
            source_context=source_context,
            first_slice=first_slice,
        ),
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

def _first_slice_with_source_targets(
    first_slice: dict[str, Any], tasks: list[dict[str, Any]], *, plan: dict[str, Any] | None = None
) -> dict[str, Any]:
    synthesis_targets = [str(target) for target in list(first_slice.get("targets") or [])]
    fallback_targets = _task_source_targets(tasks)
    if not synthesis_targets:
        fallback_targets.extend(_plan_source_targets(plan or {}))
    targets = _dedupe_strings(synthesis_targets + fallback_targets)
    if not targets:
        return first_slice
    row = dict(first_slice)
    target_limit = max(1, min(8, int(row.get("target_limit") or 8)))
    row["targets"] = targets[:target_limit]
    if not row.get("name"):
        row["name"] = semantic_first_slice_name("first_bounded_capability_slice", row["targets"])
    row.setdefault("goal", str(FALLBACK_SLICE_POLICY.get("default_goal") or "Extract one bounded capability."))
    row.setdefault(
        "steps",
        [str(step).format(primary=row["targets"][0]) for step in list(FALLBACK_SLICE_POLICY.get("steps") or [])],
    )
    row.setdefault("knowledge_rule", FALLBACK_SLICE_POLICY.get("knowledge_rule"))
    row.setdefault("selection_policy", "choose the smallest source-backed slice with explicit input and output")
    row.setdefault("handoff_expectation", "SpecWriter may rerank targets within this bounded source-backed slice")
    return row


def _task_source_targets(tasks: list[dict[str, Any]]) -> list[str]:
    targets: list[str] = []
    for task in tasks:
        if str(task.get("type") or "") == "MAP_SUBSYSTEM_BOUNDARY":
            continue
        value = task.get("target")
        values = value if isinstance(value, list) else _literal_target_list(value)
        targets.extend(str(item) for item in values if ".py:" in str(item or ""))
    return targets


def _plan_source_targets(plan: dict[str, Any]) -> list[str]:
    targets: list[str] = []
    for row in list(plan.get("capabilities_to_extract") or []):
        value = row.get("capability") if isinstance(row, dict) else row
        targets.extend(
            str(item)
            for item in _literal_target_list(value)
            if _implementation_source(str(item or ""))
            or (is_python_source_ref(str(item or "")) and ":" not in str(item or ""))
        )
    return targets


def _literal_target_list(value: object) -> list[object]:
    if isinstance(value, str) and value.startswith("["):
        try:
            parsed = ast.literal_eval(value)
            return parsed if isinstance(parsed, list) else [value]
        except (SyntaxError, ValueError):
            pass
    return [value]

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

def _fact_judgment_ledger(
    *,
    summary: dict[str, Any],
    boundaries: list[dict[str, Any]],
    capabilities: list[dict[str, Any]],
    risks: list[dict[str, Any]],
    first_slice: dict[str, Any],
) -> dict[str, Any]:
    facts: list[dict[str, Any]] = [
        {
            "claim": f"Project root is `{summary.get('root')}` with {summary.get('file_count')} files.",
            "evidence_source": "ProjectMapReport.summary",
        }
    ]
    for boundary in boundaries[:3]:
        facts.append(
            {
                "claim": f"Subsystem boundary `{boundary.get('id')}` owns {boundary.get('owned_files')}.",
                "evidence_source": "ProjectMapReport.execution/readiness",
            }
        )
    for capability in capabilities[:4]:
        facts.append(
            {
                "claim": f"Capability candidate `{capability.get('source')}` is present in analysis evidence.",
                "evidence_source": capability.get("source") or "ProjectMapReport.capabilities",
            }
        )
    judgments = [
        {
            "judgment": "Use a bounded first slice before broader subsystem redesign.",
            "based_on": [capability.get("source") for capability in capabilities[:3] if capability.get("source")],
            "confidence": 0.82 if capabilities else 0.55,
            "validation_gate": "SpecWriter must bind the selected target to input/output contracts and negative acceptance.",
        },
        {
            "judgment": f"First slice `{first_slice.get('name')}` is the preferred handoff candidate.",
            "based_on": list(first_slice.get("targets", []) or [])[:4],
            "confidence": 0.86 if first_slice.get("targets") else 0.45,
            "validation_gate": "Implementer handoff is blocked unless the first slice has source-backed targets.",
        },
    ]
    for risk in risks[:3]:
        judgments.append(
            {
                "judgment": f"Risk `{risk.get('category')}` must be carried into TechnicalSpec acceptance.",
                "based_on": [risk.get("evidence_source")],
                "confidence": 0.78,
                "validation_gate": risk.get("acceptance_gate"),
            }
        )
    return {
        "artifact_type": "FactJudgmentLedger",
        "facts": facts,
        "judgments": judgments,
        "principle": "facts are copied from evidence; judgments are decisions with confidence and validation gates",
    }

def _spec_writer_handoff_readiness(
    *,
    capabilities: list[dict[str, Any]],
    traceability: list[dict[str, Any]],
    source_context: dict[str, dict[str, Any]],
    first_slice: dict[str, Any],
) -> dict[str, Any]:
    targets = [str(item) for item in list(first_slice.get("targets", []) or []) if item]
    checks = {
        "has_source_backed_first_slice": any(_implementation_source(target) for target in targets),
        "has_capability_candidates": bool(capabilities),
        "has_traceability": bool(traceability),
        "has_source_context": bool(source_context),
    }
    if not targets and not capabilities:
        return {
            "artifact_type": "SpecWriterHandoffReadiness",
            "status": "blocked",
            "checks": checks,
            "blocked_by": ["no_safe_source_specific_candidate"],
        }
    return {
        "artifact_type": "SpecWriterHandoffReadiness",
        "status": "ready" if all(checks.values()) else "blocked",
        "checks": checks,
        "blocked_by": [key for key, ok in checks.items() if not ok],
    }
