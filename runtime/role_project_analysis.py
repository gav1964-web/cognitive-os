"""Prepare the canonical Project Analyzer handoff for configured roles."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from .project_benchmark import analyze_project
from .project_interpreter import interpret_project_report


def analyze_role_project(*, root: Path, project_dir: Path, goal: str) -> dict[str, Any]:
    outputs = analyze_project(project_dir)
    outputs["project_map_report"] = prepare_role_project_report(
        root=root,
        goal=goal,
        analyzer_outputs=outputs,
    )
    return outputs


def prepare_role_project_report(
    *,
    root: Path,
    goal: str,
    analyzer_outputs: dict[str, Any],
) -> dict[str, Any]:
    """Attach interpretation as evidence without replacing Architect authority."""

    project_map_report = dict(analyzer_outputs["project_map_report"])
    goal_report = {
        "goal_id": f"role_analysis_{Path(str(project_map_report.get('root') or '')).name or 'project'}",
        "goal": goal,
        "execution": {
            "status": "ok",
            "completed_nodes": list(analyzer_outputs),
            "outputs": analyzer_outputs,
        },
    }
    interpretation = interpret_project_report(goal_report, root=root.as_posix())
    project_map_report = enrich_weak_contract_readiness(project_map_report)
    return {
        **project_map_report,
        "level35_project_signals": interpretation.get("level35_project_signals", {}),
        "level4_project_interpretation": interpretation.get("level4_project_interpretation", {}),
        "analysis_tasks": interpretation.get("analysis_tasks", {}),
        "architecture_synthesis_advisory": interpretation.get("architecture_synthesis", {}),
        "knowledge_gap": interpretation.get("knowledge_gap"),
        "research_plan": interpretation.get("research_plan"),
        "role_analysis_contract": {
            "source": "runtime.role_project_analysis",
            "architect_authority": "configured_architect_builder",
            "interpretation_authority": "advisory_only",
        },
    }


def enrich_weak_contract_readiness(project_map_report: dict[str, Any]) -> dict[str, Any]:
    answers = dict(project_map_report.get("answers") or {})
    readiness = dict(answers.get("6_runtime_extraction_readiness") or {})
    plan = dict(readiness.get("minimal_extraction_plan") or {})
    targets = _weak_contract_targets(answers, readiness)
    if targets and not plan.get("capabilities_to_extract"):
        plan["capabilities_to_extract"] = [
            {"capability": target, "reason": "source-backed weak contract needs bounded TechnicalSpec"}
            for target in targets[:6]
        ]
        plan.pop("blocked_by", None)
    if targets and len(readiness.get("data_lifecycle") or []) < 3:
        readiness["data_lifecycle"] = [
            {"stage": "input_discovery", "shape": "source-backed test or weak-contract target", "evidence": targets[0]},
            {"stage": "contract_execution", "shape": "selected callable boundary", "evidence": targets[0]},
            {"stage": "result_or_failure", "shape": "return value, assertion, or typed failure", "evidence": targets[0]},
        ]
    readiness["minimal_extraction_plan"] = plan
    answers["6_runtime_extraction_readiness"] = readiness
    return {**project_map_report, "answers": answers}


def _weak_contract_targets(answers: dict[str, Any], readiness: dict[str, Any]) -> list[str]:
    contracts = dict(answers.get("4_contracts_data") or {})
    strategy = dict(readiness.get("contract_test_strategy") or {})
    values = [
        *list(contracts.get("weak_contract_zones") or []),
        *str(strategy.get("hand_written_negative_tests") or "").split(";"),
    ]
    return _dedupe_strings([source for value in values for source in _source_refs(value)])


def _source_refs(value: object) -> list[str]:
    if isinstance(value, list):
        return [source for item in value for source in _source_refs(item)]
    if isinstance(value, str) and value.startswith("["):
        try:
            return _source_refs(ast.literal_eval(value))
        except (SyntaxError, ValueError):
            pass
    text = str(value).strip()
    return [text] if ".py:" in text else []


def _dedupe_strings(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))
