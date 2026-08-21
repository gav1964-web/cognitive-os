"""Trial general parameter-sampling strategies after repeated search exhaustion."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from runtime.knowledge_admission import load_kb_candidates
from runtime.self_improvement_evolution_runner import evolve_diagnosed_foundation_policy

FAILURE_CLASS = "executable_sample_contract"


def run(context: dict[str, Any]) -> dict[str, Any]:
    diagnosis = dict(context.get("diagnosis") or {})
    if str(diagnosis.get("failure_class") or "") != FAILURE_CLASS:
        return {"status": "not_applicable", "reason": "failure_class_not_supported"}
    root = Path(context["root"])
    project = Path(context["project_dir"])
    minimum = int(dict(context.get("plugin_config") or {}).get("minimum_confirmed_cases") or 3)
    evidence = _search_exhaustion_evidence(root)
    if project.name in evidence:
        return {
            "status": "blocked", "reason": "independent_holdout_required",
            "evidence_projects": sorted(evidence),
        }
    independent = sorted(name for name in evidence if name)
    if len(independent) < minimum:
        return {
            "status": "blocked", "reason": "repeated_independent_evidence_required",
            "observed_project_count": len(independent), "minimum_confirmed_cases": minimum,
        }
    strategy = _strategy(context)
    if not strategy:
        return {"status": "not_applicable", "reason": "bounded_strategy_not_identified"}
    if not context.get("regression_projects"):
        return {"status": "blocked", "reason": "regression_projects_required"}
    proposal = {
        "artifact_type": "ConfigMutationProposal",
        "target": "config/executable_acceptance_policy.json",
        "operation": "merge_object",
        "path": "/structural_sample_policy",
        "content": {"parameter_strategies": {strategy: True}},
    }
    trial_diagnosis = {**diagnosis, "proposed_knowledge": {"config_mutation_proposal": proposal}}
    evolution = evolve_diagnosed_foundation_policy(
        root=root,
        project_dir=project,
        failure_packet=dict(context.get("failure_packet") or {}),
        diagnosis=trial_diagnosis,
        regression_projects=list(context.get("regression_projects") or []),
        promote=bool(context.get("promote")),
    )
    applied = bool(dict(evolution or {}).get("promotion", {}).get("applied"))
    return {
        "status": "promoted" if applied else ("trial_passed" if dict(evolution or {}).get("status") == "passed" else "blocked"),
        "reason": "" if evolution else "strategy_trial_unavailable",
        "change_type": "bounded_parameter_strategy",
        "strategy": strategy,
        "independent_evidence_projects": independent,
        "promotion_applied": applied,
        "evolution": evolution or {},
    }


def _search_exhaustion_evidence(root: Path) -> set[str]:
    projects: set[str] = set()
    for candidate in load_kb_candidates(root=root):
        if candidate.get("record_type") != "role_training_experience":
            continue
        record = dict(candidate.get("proposed_record") or {})
        conclusion = dict(record.get("trial_conclusion") or {})
        if record.get("failure_class") != FAILURE_CLASS:
            continue
        if conclusion.get("next_hypothesis") != "continue_bounded_parameter_search":
            continue
        for case in list(candidate.get("source_cases") or []):
            if isinstance(case, dict) and case.get("project"):
                projects.add(str(case["project"]))
    return projects


def _strategy(context: dict[str, Any]) -> str:
    text = json.dumps(
        {"failure_packet": context.get("failure_packet"), "diagnosis": context.get("diagnosis")},
        ensure_ascii=False,
    ).lower()
    if re.search(r"keyerror[^0-9]{0,20}0", text):
        return "indexed_sequence"
    if "keyerror" in text or "missing required key" in text:
        return "nested_mapping_paths"
    if "missing 1 required positional argument" in text or "lambda" in text and "positional" in text:
        return "callable_arity"
    if "invalid literal for int" in text or "integer input" in text:
        return "derived_conversion"
    return ""
