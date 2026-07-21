"""Answer helpers for role questionnaire sections."""

from __future__ import annotations

from typing import Any


def _compact(value: Any) -> str:
    if value is None or value == "":
        return "unknown"
    if isinstance(value, str):
        return value[:800]
    if isinstance(value, dict):
        items = []
        for key, item in list(value.items())[:8]:
            compact = _compact(item)
            if compact != "unknown":
                items.append(f"{key}: {compact}")
        return "; ".join(items)[:1000] if items else "{}"
    if isinstance(value, list):
        parts = [_compact(item) for item in value[:8]]
        parts = [part for part in parts if part != "unknown"]
        return "; ".join(parts)[:1000] if parts else "[]"
    return str(value)[:800]


def _architecture_field(ctx: _Context, name: str) -> Any:
    knowledge = dict(ctx.architecture.get("knowledge", {}))
    aliases = {
        "matched_rule": knowledge.get("matched_rule"),
        "knowledge_matches": {
            "matched_rule": knowledge.get("matched_rule"),
            "matched_because": knowledge.get("matched_because"),
            "candidate_rules": knowledge.get("candidate_rules"),
            "capability_patterns": ctx.architecture.get("matched_capability_patterns"),
            "risk_patterns": ctx.architecture.get("matched_risk_patterns"),
        },
        "target_shape": ctx.architecture.get("target_architecture_shape"),
    }
    return aliases.get(name) or ctx.architecture.get(name) or ctx.architecture.get(name.replace("_", "-"))


def _minimal_plan(ctx: _Context) -> Any:
    return ctx.readiness.get("minimal_extraction_plan")


def _capability_candidates(ctx: _Context) -> Any:
    plan = ctx.readiness.get("minimal_extraction_plan")
    if isinstance(plan, dict) and plan.get("capabilities_to_extract"):
        return plan.get("capabilities_to_extract")
    return ctx.capabilities.get("atomic_reusable_capabilities") or ctx.capabilities.get("pure_transforms")


def _first_capability(ctx: _Context) -> str:
    plan = ctx.readiness.get("minimal_extraction_plan")
    if isinstance(plan, dict):
        rows = plan.get("capabilities_to_extract")
        if isinstance(rows, list) and rows:
            first = rows[0]
            if isinstance(first, dict):
                return str(first.get("capability") or first.get("source") or first.get("target") or "unknown")
            return str(first)
        rows = plan.get("capabilities")
        if isinstance(rows, list) and rows:
            return str(rows[0])
    values = _capability_candidates(ctx)
    if isinstance(values, list) and values:
        first = values[0]
        if isinstance(first, dict):
            return str(first.get("path") or first.get("name") or first)
        return str(first)
    return "unknown"


def _external_surface(ctx: _Context) -> dict[str, Any]:
    return {
        "external_imports": ctx.insights.get("external_imports"),
        "side_effects": ctx.readiness.get("idempotency_risks"),
        "quarantine_candidates": ctx.readiness.get("quarantine_candidates"),
    }


def _confidence(ctx: _Context) -> dict[str, Any]:
    signals = dict(ctx.interpretation.get("level35_project_signals", {}))
    return {
        "signals": signals.get("confidence"),
        "synthesis": ctx.architecture.get("confidence"),
        "knowledge_gap": bool(ctx.knowledge_gap),
    }


def _non_goals(ctx: _Context) -> list[str]:
    return [
        "no whole-project rewrite",
        "no direct source edit during questionnaire/probe",
        "avoid docs/tests/examples as first extraction target",
        *([f"avoid {item}" for item in ctx.readiness.get("source_strata", {}).get("legacy_noise", [])[:3]] if isinstance(ctx.readiness.get("source_strata"), dict) else []),
    ]


def _manual_decisions(ctx: _Context) -> Any:
    return [task for task in ctx.tasks if isinstance(task, dict) and task.get("type") in {"REVIEW_HUMAN_DECISION", "ANSWER_OPEN_QUESTION"}][:6]


def _spec_contract_target(ctx: _Context) -> dict[str, str]:
    return {"candidate": _first_capability(ctx), "handoff": "ArchitectureDecisionRecord -> TechnicalSpec"}


def _contract_field(ctx: _Context, key: str, target: str) -> Any:
    return ctx.contracts.get(key) or {"target": target, "status": "derive from signature/type hints/docstrings/tests"}


def _goal_spec(ctx: _Context, target: str) -> dict[str, str]:
    return {
        "goal": f"Extract or harden {target} as the first bounded capability.",
        "project_goal": str(dict(ctx.goal_report).get("goal") or ""),
    }


def _acceptance_criteria(ctx: _Context, target: str) -> list[str]:
    criteria = [
        f"{target} has explicit input/output contract.",
        "existing entrypoint behavior remains unchanged.",
        "negative tests cover bad input and external failure paths.",
    ]
    criteria.extend(str(task.get("acceptance")) for task in ctx.tasks[:4] if isinstance(task, dict) and task.get("acceptance"))
    return criteria[:8]


def _error_surface(ctx: _Context) -> Any:
    return {
        "errors": ctx.errors.get("error_types"),
        "explicit_handling": ctx.errors.get("explicit_error_handling"),
        "falls_through": ctx.errors.get("unhandled_exceptions"),
    }


def _spec_out_of_scope(ctx: _Context) -> list[str]:
    return ["project-wide rewrite", "dependency upgrade without separate review", "registry mutation", "self-learning KB admission"]


def _open_questions(ctx: _Context) -> Any:
    manual = _manual_decisions(ctx)
    return manual or ctx.knowledge_gap or "No explicit open question was detected; verify scope manually before implementation."


def _verification_artifacts(ctx: _Context, target: str) -> list[str]:
    return [f"contract tests for {target}", "smoke command result", "review findings", "known limitations"]


def _adapter_candidates(ctx: _Context) -> dict[str, Any]:
    return {"entrypoints": ctx.execution.get("entrypoints"), "external_imports": ctx.insights.get("external_imports")}


def _patch_strategy(ctx: _Context, target: str) -> list[str]:
    return [f"prepare isolated patch for {target}", "run tests before promotion", "require reviewer approval before source mutation"]


def _implementation_blockers(ctx: _Context) -> Any:
    plan = ctx.readiness.get("minimal_extraction_plan")
    if isinstance(plan, dict) and plan.get("blocked_by"):
        return plan.get("blocked_by")
    return _open_questions(ctx)


def _rollout_plan(ctx: _Context, target: str) -> list[str]:
    return [f"extract/harden {target}", "add contract tests", "run smoke command", "publish ReviewFindings"]


def _test_surface(ctx: _Context) -> Any:
    return ctx.insights.get("test_surface") or ctx.summary.get("tests")


def _contract_tests(ctx: _Context, target: str) -> list[str]:
    return [f"valid input -> expected output for {target}", f"invalid input -> typed error for {target}"]


def _negative_tests(ctx: _Context) -> Any:
    return ctx.readiness.get("quarantine_candidates") or ctx.errors.get("error_types")


def _fixtures(ctx: _Context) -> Any:
    imports = ctx.insights.get("external_imports")
    return imports or "No external fixture target detected."


def _smoke_test(ctx: _Context) -> Any:
    return ctx.runtime_commands.get("commands") or ctx.execution.get("entrypoints")


def _regression_tests(ctx: _Context, target: str) -> list[str]:
    return [f"entrypoint still reaches {target}", "primary execution path remains stable"]


def _test_gaps(ctx: _Context) -> Any:
    return {"test_surface": _test_surface(ctx), "open_questions": _open_questions(ctx)}


def _test_priority(ctx: _Context, target: str) -> list[str]:
    return [f"contract tests for {target}", "negative tests", "smoke tests", "idempotency/replay tests"]


def _blocking_risks(ctx: _Context) -> Any:
    risks = ctx.project_report.get("risks") or []
    p1 = [task for task in ctx.tasks if isinstance(task, dict) and task.get("priority") == "P1"]
    return {"risks": risks, "p1_tasks": p1}


def _security_risks(ctx: _Context) -> Any:
    text = _compact(_external_surface(ctx)).lower()
    hits = [word for word in ("auth", "token", "secret", "password", "network", "http") if word in text]
    return hits or "No explicit security keyword was detected in analyzer evidence."


def _observability(ctx: _Context) -> Any:
    return ctx.insights.get("logging") or "No explicit observability summary detected."


def _source_noise(ctx: _Context) -> Any:
    strata = ctx.readiness.get("source_strata")
    return strata if strata else "No source strata evidence; reviewer should verify docs/tests/examples were not selected."


def _ambiguous_facts(ctx: _Context) -> Any:
    return _open_questions(ctx)


def _kb_impact(ctx: _Context) -> Any:
    return {"matched_rule": _architecture_field(ctx, "matched_rule"), "knowledge_gap": ctx.knowledge_gap}


def _release_decision(ctx: _Context) -> str:
    if _first_capability(ctx) == "unknown":
        return "request_rework: no bounded target"
    if ctx.project_report.get("risks"):
        return "approve_with_risks: bounded first slice only"
    return "approve: bounded first slice"


def _approvals(ctx: _Context) -> list[str]:
    return ["human approval before source edit", "reviewer approval before promotion", "KB admission approval before knowledge merge"]


def _official_docs_need(ctx: _Context) -> Any:
    return bool(ctx.knowledge_gap or ctx.insights.get("external_imports"))


def _package_metadata_need(ctx: _Context) -> Any:
    return bool(ctx.summary.get("frameworks") or ctx.insights.get("external_imports"))


def _comparable_repo_need(ctx: _Context) -> Any:
    return bool(ctx.knowledge_gap)


def _kb_candidates(ctx: _Context) -> Any:
    return ctx.knowledge_gap or _architecture_field(ctx, "matched_rule") or "No KB candidate without repeated confirmation."


def _facts_vs_judgments(ctx: _Context) -> dict[str, list[str]]:
    return {
        "facts": ["ProjectMapReport.summary", "ProjectMapReport.answers", "extract_python_structure"],
        "judgments": ["architecture_synthesis", "role questionnaire recommendations", "release decision"],
    }


def _kb_confirmations(ctx: _Context) -> list[str]:
    return ["repeat on several projects", "human/Codex review", "evidence-backed admission record"]


def _freshness(ctx: _Context) -> str:
    return "Local source facts are fresh at analysis time; external facts require source date/version checks."


def _allowed_sources(ctx: _Context) -> list[str]:
    return ["local project source", "official documentation", "package metadata", "GitHub repositories as comparative evidence"]


def _unresolved_sources(ctx: _Context) -> Any:
    return ctx.research_plan or "No active research plan."


def _admission_status(ctx: _Context) -> str:
    return "candidate_only: requires repeated evidence and human/Codex approval"
