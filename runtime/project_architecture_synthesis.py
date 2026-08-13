"""Knowledge-backed architecture synthesis for project-analysis reports."""

from __future__ import annotations

import ast
import hashlib
from pathlib import Path
from typing import Any

from .architecture_synthesis_policy import load_architecture_synthesis_policy
from .architecture_slice_naming import semantic_first_slice_name
from .knowledge_usage_telemetry import record_knowledge_usage
from .role_knowledge import role_knowledge_distribution
from .project_facts import facts_from_project_report, llm_fact_digest
from .project_architecture_knowledge import (
    CAPABILITY_PATTERNS_PATH,
    KNOWLEDGE_PATH,
    PROJECT_LESSONS_PATH,
    RISK_PATTERNS_PATH,
    load_all_knowledge_records,
    load_architecture_knowledge,
    match_architecture_rule,
    match_capability_patterns,
    match_project_lessons,
    match_risk_patterns,
)


ARCHITECTURE_SYNTHESIS_POLICY = load_architecture_synthesis_policy()


def synthesize_project_architecture(
    report: dict[str, Any],
    *,
    level35_signals: dict[str, Any],
    level4_interpretation: dict[str, Any],
    analysis_tasks: dict[str, Any],
    root: Path | str | None = None,
) -> dict[str, Any]:
    """Turn facts, impulses, and backlog into a project-specific strategy."""

    facts = facts_from_project_report(report)
    digest = llm_fact_digest(facts)
    knowledge = load_architecture_knowledge()
    match = match_architecture_rule(digest, knowledge)
    rule = match["rule"]
    record_knowledge_usage(
        event_type="kb_rule_match",
        role="architect",
        source="architecture_patterns",
        root=root,
        rule_id=str(rule.get("rule_id") or ""),
        status="matched",
        confidence=_confidence(digest, _bottlenecks(digest, analysis_tasks), match),
        query=str(digest.get("root") or ""),
        details={
            "score": match.get("score"),
            "matched_because": match.get("matched_because", []),
            "candidate_count": len(match.get("candidate_rules", [])),
        },
    )
    profile = _profile(digest, rule, match)
    bottlenecks = _bottlenecks(digest, analysis_tasks)
    first_slice = _first_slice(rule, digest, analysis_tasks, knowledge)
    capability_patterns = match_capability_patterns(digest)
    risk_patterns = match_risk_patterns(digest)
    lessons = match_project_lessons(rule, capability_patterns, risk_patterns)
    role_distribution = role_knowledge_distribution(load_all_knowledge_records())
    return {
        "artifact_type": "ProjectArchitectureSynthesis",
        "layer": "L4",
        "source": "knowledge_backed_architecture_synthesis",
        "synthesis_id": _synthesis_id(digest, first_slice),
        "knowledge": {
            "path": KNOWLEDGE_PATH.as_posix(),
            "schema_version": knowledge.get("schema_version"),
            "matched_rule": rule.get("rule_id"),
            "matched_because": match.get("matched_because", []),
            "candidate_rules": match.get("candidate_rules", []),
            "capability_patterns_path": CAPABILITY_PATTERNS_PATH.as_posix(),
            "risk_patterns_path": RISK_PATTERNS_PATH.as_posix(),
            "project_lessons_path": PROJECT_LESSONS_PATH.as_posix(),
        },
        "project_profile": profile,
        "project_diagnosis": _diagnosis(rule, profile, digest, bottlenecks, knowledge),
        "target_architecture_shape": _target_shape(rule, digest),
        "top_bottlenecks": bottlenecks[:3],
        "matched_capability_patterns": capability_patterns,
        "matched_risk_patterns": risk_patterns,
        "relevant_lessons": lessons,
        "role_knowledge_distribution": role_distribution,
        "recommended_first_slice": first_slice,
        "what_not_to_touch_yet": _defer(rule),
        "verification_plan": _verification(rule, digest, first_slice),
        "task_focus": _task_focus(analysis_tasks),
        "evidence": {
            "entrypoints": digest.get("entrypoints", [])[:5],
            "central_flow": digest.get("central", [])[:5],
            "broad_functions": digest.get("broad", [])[:5],
            "capability_candidates": digest.get("capabilities", [])[:6],
            "runtime_extraction": digest.get("runtime_extraction", {}),
            "risk_codes": digest.get("risks", [])[:6],
            "level35_signal_count": len(level35_signals.get("signals", [])) if isinstance(level35_signals, dict) else 0,
            "level4_confidence": level4_interpretation.get("confidence") if isinstance(level4_interpretation, dict) else None,
        },
        "confidence": _confidence(digest, bottlenecks, match),
    }

def _profile(facts: dict[str, Any], rule: dict[str, Any], match: dict[str, Any]) -> dict[str, Any]:
    domain_profile = dict(facts.get("domain_profile") or {})
    return {
        "archetype": rule.get("archetype"),
        "label": rule.get("label"),
        "domain_profile": domain_profile,
        "domain_profile_kind": domain_profile.get("kind"),
        "purpose_summary": rule.get("purpose_summary"),
        "scenario_summary": _strings(rule.get("scenario_summary"))[:6],
        "input_summary": _strings(rule.get("input_summary"))[:8],
        "output_summary": _strings(rule.get("output_summary"))[:8],
        "root": str(facts.get("root") or ""),
        "frameworks": [str(item) for item in facts.get("frameworks", [])],
        "inputs": [str(item) for item in facts.get("inputs", [])],
        "outputs": [str(item) for item in facts.get("outputs", [])],
        "routes_count": int(facts.get("routes_count") or 0),
        "knowledge_rule": rule.get("rule_id"),
        "knowledge_score": match.get("score"),
    }


def _diagnosis(rule: dict[str, Any], profile: dict[str, Any], facts: dict[str, Any], bottlenecks: list[dict[str, Any]], knowledge: dict[str, Any]) -> str:
    entrypoints = _entrypoint_summary(facts, knowledge)
    main = str(facts.get("task") or "project purpose is inferred from structure")
    target = _primary_target(rule, facts, bottlenecks)
    diagnosis = dict(rule.get("diagnosis") or {})
    template = diagnosis.get("template")
    if template:
        return str(template).format(label=profile["label"], entrypoints=entrypoints, target=target, main=main)
    return f"{profile['label']} with entrypoint {entrypoints}; {main}. The first architectural pressure point is {target}."


def _entrypoint_summary(facts: dict[str, Any], knowledge: dict[str, Any]) -> str:
    entrypoints = [str(item) for item in facts.get("entrypoints", []) if item]
    active_entrypoints = [item for item in entrypoints if not _is_context_only_target(item, knowledge)]
    if active_entrypoints:
        return ", ".join(active_entrypoints[:3])
    core_flow_paths = []
    for target in list(facts.get("central", [])) + list(facts.get("broad", [])):
        path = _target_path(str(target))
        if path and not _is_context_only_target(path, knowledge) and path not in core_flow_paths:
            core_flow_paths.append(path)
    if core_flow_paths:
        return "core flow in " + ", ".join(core_flow_paths[:3])
    if entrypoints:
        return ", ".join(entrypoints[:3])
    return "unknown entrypoint"


def _target_shape(rule: dict[str, Any], facts: dict[str, Any]) -> list[str]:
    rows = _strings(rule.get("target_architecture_shape"))
    if rows:
        return rows
    capabilities = ", ".join(facts.get("capabilities", [])[:3]) or "candidate capabilities"
    return [str(item).format(capabilities=capabilities) for item in _strings(ARCHITECTURE_SYNTHESIS_POLICY.get("fallback_target_shape"))]


def _bottlenecks(facts: dict[str, Any], analysis_tasks: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    runtime = dict(facts.get("runtime_extraction", {}))
    for rule in _bottleneck_rules():
        source = str(rule.get("source") or "")
        limit = int(rule.get("limit") or 0)
        items: list[Any] = []
        if source == "runtime_extraction.process_boundary":
            items = list(runtime.get("process_boundary", []))
        elif source == "runtime_extraction.orchestrators":
            items = list(runtime.get("orchestrators", []))
        elif source == "runtime_extraction.idempotency":
            items = list(runtime.get("idempotency", []))
        elif source == "facts.broad":
            items = list(facts.get("broad", []))
        elif source == "analysis_tasks":
            task_types = {str(item) for item in list(rule.get("task_types") or [])}
            items = [task for task in _tasks(analysis_tasks) if str(task.get("type") or "") in task_types]
        for item in items[:limit]:
            target = str(item.get("target") or "") if isinstance(item, dict) and source == "analysis_tasks" else _target(item)
            rows.append(
                _bottleneck(
                    str(rule.get("kind") or source),
                    target,
                    str(rule.get("reason") or "architecture policy matched this target"),
                    str(rule.get("severity") or "medium"),
                )
            )
    return _dedupe_bottlenecks(rows)


def _first_slice(rule: dict[str, Any], facts: dict[str, Any], analysis_tasks: dict[str, Any], knowledge: dict[str, Any]) -> dict[str, Any]:
    recipe = dict(rule.get("first_slice") or {})
    if recipe:
        rows = _source_targets(recipe.get("target_sources"), facts, analysis_tasks)
        targets = _prefer_targets(rows, _strings(recipe.get("targets_prefer")), knowledge)[:4]
        return {
            "name": semantic_first_slice_name(str(recipe.get("name") or "first_bounded_capability_slice"), targets),
            "goal": str(recipe.get("goal") or "Extract one useful capability with explicit input/output and tests."),
            "targets": targets,
            "steps": _strings(recipe.get("steps")),
            "knowledge_rule": rule.get("rule_id"),
        }
    targets = _targets_by_type(analysis_tasks, {str(item) for item in list(_default_first_slice_policy().get("target_task_types") or [])})[:3]
    return {
        "name": semantic_first_slice_name(str(_default_first_slice_policy().get("name") or "first_bounded_capability_slice"), targets),
        "goal": str(_default_first_slice_policy().get("goal") or "Extract one useful capability with explicit input/output and tests."),
        "targets": targets,
        "steps": _strings(_default_first_slice_policy().get("steps")),
        "knowledge_rule": rule.get("rule_id"),
    }


def _defer(rule: dict[str, Any]) -> list[str]:
    return _strings(dict(ARCHITECTURE_SYNTHESIS_POLICY.get("defer") or {}).get("default_items")) + _strings(rule.get("defer"))


def _verification(rule: dict[str, Any], facts: dict[str, Any], first_slice: dict[str, Any]) -> list[str]:
    tests = facts.get("tests", {})
    existing = tests.get("test_files_seen", tests.get("test_files", 0)) if isinstance(tests, dict) else 0
    plan = [
        str(item).format(slice_name=first_slice["name"], existing_tests=existing)
        for item in _strings(dict(ARCHITECTURE_SYNTHESIS_POLICY.get("verification") or {}).get("default_steps"))
    ]
    extra = str(rule.get("verification_extra") or "").strip()
    if extra:
        plan.append(extra)
    return plan


def _task_focus(analysis_tasks: dict[str, Any]) -> list[dict[str, Any]]:
    focus = dict(ARCHITECTURE_SYNTHESIS_POLICY.get("task_focus") or {})
    preferred = {str(key): int(value) for key, value in dict(focus.get("preferred_order") or {}).items()}
    default_rank = int(focus.get("default_rank") or 20)
    limit = int(focus.get("limit") or 6)
    rows = sorted(_tasks(analysis_tasks), key=lambda row: (preferred.get(str(row.get("type")), default_rank), str(row.get("target"))))
    return [{"type": row.get("type"), "target": row.get("target"), "why": row.get("acceptance")} for row in rows[:limit]]


def _primary_target(rule: dict[str, Any], facts: dict[str, Any], bottlenecks: list[dict[str, Any]]) -> str:
    diagnosis = dict(rule.get("diagnosis") or {})
    rows = _source_targets(diagnosis.get("primary_sources"), facts, {}, bottlenecks=bottlenecks)
    fallback = str(dict(ARCHITECTURE_SYNTHESIS_POLICY.get("primary_target") or {}).get("fallback") or "no dominant hotspot")
    return (_prefer_targets(rows, _strings(diagnosis.get("primary_target_prefer")), load_architecture_knowledge()) or [fallback])[0]


def _source_targets(sources: Any, facts: dict[str, Any], analysis_tasks: dict[str, Any], *, bottlenecks: list[dict[str, Any]] | None = None) -> list[str]:
    runtime = dict(facts.get("runtime_extraction", {}))
    rows: list[str] = []
    for source in _strings(sources):
        if source == "central":
            rows.extend(str(item) for item in facts.get("central", []))
        elif source == "broad":
            rows.extend(str(item) for item in facts.get("broad", []))
        elif source == "domain_anchors":
            rows.extend(str(item) for item in facts.get("domain_anchors", []))
        elif source == "extraction":
            rows.extend(str(row.get("capability") or "") for row in runtime.get("extraction", []) if isinstance(row, dict))
        elif source == "process_boundary":
            rows.extend(_target(item) for item in runtime.get("process_boundary", []))
        elif source == "orchestrators":
            rows.extend(str(item) for item in runtime.get("orchestrators", []))
        elif source == "tasks":
            rows.extend(_targets_by_type(analysis_tasks, {"DRAFT_PIPELINE_CAPABILITY", "EXTRACT_CAPABILITY"}))
        elif source == "bottlenecks" and bottlenecks:
            rows.extend(str(row.get("target") or "") for row in bottlenecks)
    return [row for row in rows if row]


def _prefer_targets(rows: list[str], needles: list[str], knowledge: dict[str, Any]) -> list[str]:
    selected: list[str] = []
    for needle in needles:
        match = _find_contains(rows, needle)
        if match and match not in selected:
            selected.append(match)
    for row in rows:
        if row not in selected:
            selected.append(row)
    active = [row for row in selected if not _is_context_only_target(row, knowledge)]
    context = [row for row in selected if _is_context_only_target(row, knowledge)]
    return active + context


def _confidence(facts: dict[str, Any], bottlenecks: list[dict[str, Any]], match: dict[str, Any]) -> str:
    policy = dict(ARCHITECTURE_SYNTHESIS_POLICY.get("confidence") or {})
    high_ok = True
    if policy.get("high_requires_entrypoints", True):
        high_ok = high_ok and bool(facts.get("entrypoints"))
    if policy.get("high_requires_capabilities", True):
        high_ok = high_ok and bool(facts.get("capabilities"))
    if policy.get("high_requires_bottlenecks", True):
        high_ok = high_ok and bool(bottlenecks)
    high_ok = high_ok and int(match.get("score") or 0) > int(policy.get("high_min_match_score_exclusive") or 1)
    if high_ok:
        return "high"
    if any(facts.get(str(field)) for field in list(policy.get("medium_requires_any") or ["entrypoints", "capabilities"])):
        return "medium"
    return "low"


def _targets_by_type(analysis_tasks: dict[str, Any], task_types: set[str]) -> list[str]:
    return [target for row in _tasks(analysis_tasks) if row.get("type") in task_types for target in _target_values(row.get("target"))]


def _target_values(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if item]
    if isinstance(value, str) and value.startswith("["):
        try:
            return _target_values(ast.literal_eval(value))
        except (SyntaxError, ValueError):
            pass
    return [str(value)] if value else []


def _tasks(analysis_tasks: dict[str, Any]) -> list[dict[str, Any]]:
    rows = analysis_tasks.get("tasks", []) if isinstance(analysis_tasks, dict) else []
    return [row for row in rows if isinstance(row, dict)]


def _bottleneck(kind: str, target: str, reason: str, severity: str) -> dict[str, str]:
    return {"kind": kind, "target": target, "reason": reason, "severity": severity}


def _dedupe_bottlenecks(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    seen = set()
    policy = dict(ARCHITECTURE_SYNTHESIS_POLICY.get("bottlenecks") or {})
    severity_order = {str(key): int(value) for key, value in dict(policy.get("severity_order") or {}).items()}
    kind_order = {str(key): int(value) for key, value in dict(policy.get("kind_order") or {}).items()}
    for row in rows:
        target = str(row.get("target") or "")
        if not target or target in seen:
            continue
        seen.add(target)
        result.append(row)
    return sorted(
        result,
        key=lambda row: (
            severity_order.get(str(row.get("severity")), 9),
            kind_order.get(str(row.get("kind")), 20),
            str(row.get("target")),
        ),
    )


def _target(item: Any) -> str:
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        return str(item.get("target") or item.get("capability") or "")
    return ""


def _strings(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item)]
    if value in (None, "", []):
        return []
    return [str(value)]


def _find_contains(rows: list[str], needle: str) -> str:
    needle = needle.lower()
    for row in rows:
        if needle in str(row).lower():
            return str(row)
    return ""


def _is_context_only_target(target: str, knowledge: dict[str, Any]) -> bool:
    parts = _target_path(target).lower().replace("\\", "/").split("/")
    context_parts = set(_strings(dict(knowledge.get("source_scope_policy") or {}).get("context_only_parts")))
    return any(part in context_parts or _is_generated_context_part(part) for part in parts)


def _is_generated_context_part(part: str) -> bool:
    return part == "generated" or part.startswith("generated_") or part.startswith("generated-")


def _target_path(target: str) -> str:
    return str(target).split(":", 1)[0]


def _synthesis_id(facts: dict[str, Any], first_slice: dict[str, Any]) -> str:
    seed = f"{facts.get('root')}:{first_slice.get('name')}:{','.join(first_slice.get('targets', [])[:4])}"
    return "archsyn_" + hashlib.sha256(seed.encode("utf-8", errors="replace")).hexdigest()[:12]


def _default_first_slice_policy() -> dict[str, Any]:
    return dict(ARCHITECTURE_SYNTHESIS_POLICY.get("default_first_slice") or {})


def _bottleneck_rules() -> list[dict[str, Any]]:
    return [dict(row) for row in list(dict(ARCHITECTURE_SYNTHESIS_POLICY.get("bottlenecks") or {}).get("rules") or []) if isinstance(row, dict)]
