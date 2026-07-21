"""Knowledge-backed architecture synthesis for project-analysis reports."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

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


def synthesize_project_architecture(
    report: dict[str, Any],
    *,
    level35_signals: dict[str, Any],
    level4_interpretation: dict[str, Any],
    analysis_tasks: dict[str, Any],
) -> dict[str, Any]:
    """Turn facts, impulses, and backlog into a project-specific strategy."""

    facts = facts_from_project_report(report)
    digest = llm_fact_digest(facts)
    knowledge = load_architecture_knowledge()
    match = match_architecture_rule(digest, knowledge)
    rule = match["rule"]
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
    return {
        "archetype": rule.get("archetype"),
        "label": rule.get("label"),
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
    return [
        "Keep entrypoints thin and move decisions into named application services.",
        f"Extract first reusable capabilities around {capabilities}.",
        "Wrap side-effecting dependencies behind adapters with timeout and failure contracts.",
    ]


def _bottlenecks(facts: dict[str, Any], analysis_tasks: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    runtime = dict(facts.get("runtime_extraction", {}))
    for item in runtime.get("process_boundary", [])[:3]:
        rows.append(_bottleneck("process_boundary", _target(item), "network/subprocess/filesystem work needs isolation", "high"))
    for target in runtime.get("orchestrators", [])[:3]:
        rows.append(_bottleneck("hidden_orchestration", target, "control flow is implicit and hard to replay", "high"))
    for target in facts.get("broad", [])[:3]:
        rows.append(_bottleneck("broad_function", target, "too many responsibilities behind one callable", "high"))
    for item in runtime.get("idempotency", [])[:3]:
        rows.append(_bottleneck("replay_safety", _target(item), "retry or replay can duplicate side effects", "medium"))
    for task in _tasks(analysis_tasks)[:8]:
        if task.get("type") in {"DRAFT_PIPELINE_CAPABILITY", "EXTRACT_CAPABILITY"}:
            rows.append(_bottleneck("extraction_candidate", str(task.get("target") or ""), "candidate can become a first bounded pipeline step", "medium"))
    return _dedupe_bottlenecks(rows)


def _first_slice(rule: dict[str, Any], facts: dict[str, Any], analysis_tasks: dict[str, Any], knowledge: dict[str, Any]) -> dict[str, Any]:
    recipe = dict(rule.get("first_slice") or {})
    if recipe:
        rows = _source_targets(recipe.get("target_sources"), facts, analysis_tasks)
        targets = _prefer_targets(rows, _strings(recipe.get("targets_prefer")), knowledge)[:4]
        return {
            "name": str(recipe.get("name") or "first_bounded_capability_slice"),
            "goal": str(recipe.get("goal") or "Extract one useful capability with explicit input/output and tests."),
            "targets": targets,
            "steps": _strings(recipe.get("steps")),
            "knowledge_rule": rule.get("rule_id"),
        }
    return {
        "name": "first_bounded_capability_slice",
        "goal": "Extract one useful capability with explicit input/output and tests.",
        "targets": _targets_by_type(analysis_tasks, {"DRAFT_PIPELINE_CAPABILITY", "EXTRACT_CAPABILITY"})[:3],
        "steps": [
            "Select one central callable with low external coupling.",
            "Define input/output schema from signature and tests.",
            "Move side effects behind a named adapter.",
            "Add contract and negative tests.",
        ],
        "knowledge_rule": rule.get("rule_id"),
    }


def _defer(rule: dict[str, Any]) -> list[str]:
    return ["Do not rewrite the whole project before one slice has passing contract tests."] + _strings(rule.get("defer"))


def _verification(rule: dict[str, Any], facts: dict[str, Any], first_slice: dict[str, Any]) -> list[str]:
    tests = facts.get("tests", {})
    existing = tests.get("test_files_seen", tests.get("test_files", 0)) if isinstance(tests, dict) else 0
    plan = [
        f"Create or extend focused tests for slice `{first_slice['name']}`; current detected test files: {existing}.",
        "Add one happy-path contract test and one malformed-input or failed-dependency test.",
        "Record before/after ProjectMapReport to confirm fewer mixed responsibilities or clearer capability boundary.",
    ]
    extra = str(rule.get("verification_extra") or "").strip()
    if extra:
        plan.append(extra)
    return plan


def _task_focus(analysis_tasks: dict[str, Any]) -> list[dict[str, Any]]:
    preferred = {
        "DRAFT_PIPELINE_CAPABILITY": 0,
        "MAKE_ORCHESTRATION_EXPLICIT": 1,
        "ISOLATE_PROCESS_BOUNDARY": 2,
        "SPLIT_MIXED_RESPONSIBILITY": 3,
        "HARDEN_CONTRACT": 4,
        "ADD_IDEMPOTENCY_GUARD": 5,
        "DEFINE_CHECKPOINT_POLICY": 6,
    }
    rows = sorted(_tasks(analysis_tasks), key=lambda row: (preferred.get(str(row.get("type")), 20), str(row.get("target"))))
    return [{"type": row.get("type"), "target": row.get("target"), "why": row.get("acceptance")} for row in rows[:6]]


def _primary_target(rule: dict[str, Any], facts: dict[str, Any], bottlenecks: list[dict[str, Any]]) -> str:
    diagnosis = dict(rule.get("diagnosis") or {})
    rows = _source_targets(diagnosis.get("primary_sources"), facts, {}, bottlenecks=bottlenecks)
    return (_prefer_targets(rows, _strings(diagnosis.get("primary_target_prefer")), load_architecture_knowledge()) or ["no dominant hotspot"])[0]


def _source_targets(sources: Any, facts: dict[str, Any], analysis_tasks: dict[str, Any], *, bottlenecks: list[dict[str, Any]] | None = None) -> list[str]:
    runtime = dict(facts.get("runtime_extraction", {}))
    rows: list[str] = []
    for source in _strings(sources):
        if source == "central":
            rows.extend(str(item) for item in facts.get("central", []))
        elif source == "broad":
            rows.extend(str(item) for item in facts.get("broad", []))
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
    if facts.get("entrypoints") and facts.get("capabilities") and bottlenecks and int(match.get("score") or 0) > 1:
        return "high"
    if facts.get("entrypoints") or facts.get("capabilities"):
        return "medium"
    return "low"


def _targets_by_type(analysis_tasks: dict[str, Any], task_types: set[str]) -> list[str]:
    return [str(row.get("target")) for row in _tasks(analysis_tasks) if row.get("type") in task_types and row.get("target")]


def _tasks(analysis_tasks: dict[str, Any]) -> list[dict[str, Any]]:
    rows = analysis_tasks.get("tasks", []) if isinstance(analysis_tasks, dict) else []
    return [row for row in rows if isinstance(row, dict)]


def _bottleneck(kind: str, target: str, reason: str, severity: str) -> dict[str, str]:
    return {"kind": kind, "target": target, "reason": reason, "severity": severity}


def _dedupe_bottlenecks(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    seen = set()
    severity_order = {"high": 0, "medium": 1, "low": 2}
    kind_order = {
        "hidden_orchestration": 0,
        "broad_function": 1,
        "process_boundary": 2,
        "replay_safety": 3,
        "extraction_candidate": 4,
    }
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
    return any(part in context_parts for part in parts)


def _target_rank(target: str, knowledge: dict[str, Any]) -> tuple[int, int, str]:
    path = _target_path(target).lower().replace("\\", "/")
    policy = dict(knowledge.get("source_scope_policy") or {})
    context_penalty = 10 if _is_context_only_target(target, knowledge) else 0
    prefixes = tuple(_strings(policy.get("prefer_core_prefixes")))
    files = set(_strings(policy.get("prefer_core_files")))
    name = path.rsplit("/", 1)[-1]
    core_bonus = 0 if path.startswith(prefixes) or name in files else 1
    return (context_penalty, core_bonus, path)


def _target_path(target: str) -> str:
    return str(target).split(":", 1)[0]


def _synthesis_id(facts: dict[str, Any], first_slice: dict[str, Any]) -> str:
    seed = f"{facts.get('root')}:{first_slice.get('name')}:{','.join(first_slice.get('targets', [])[:4])}"
    return "archsyn_" + hashlib.sha256(seed.encode("utf-8", errors="replace")).hexdigest()[:12]
