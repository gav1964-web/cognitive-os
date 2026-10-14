"""Resolve non-selection hypotheses through bounded plugin contracts."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .hypothesis_compiler_contract import capability_request
from .hypothesis_compiler_evidence import compact_report
from .hypothesis_compiler_repository_gate import (
    capture_selection_state, rollback_selection_state, run_repository_gate,
)
from .project_evolution_policy import load_project_evolution_policy
from .self_improvement_plugin_foundry import resolve_plugin_requests


DIRECT_TRIAL_TYPES = {"semantic_contract_profile", "executable_adapter"}
EVIDENCE_PLAN_TYPE = "evidence_collection_plan"


def run_specialized_trials(
    *, root: Path, hypotheses: list[dict[str, Any]], history: list[dict[str, Any]],
    candidate_types: set[str] | None, promote: bool, maximum_holdouts: int,
    hypothesis_ids: set[str] | None = None, maximum_promotions: int = 0, progress=None,
) -> list[dict[str, Any]]:
    selected = [
        row for row in hypotheses
        if row.get("candidate_type") != "candidate_selection_rule"
        and (candidate_types is None or str(row.get("candidate_type")) in candidate_types)
        and (hypothesis_ids is None or str(row.get("hypothesis_id")) in hypothesis_ids)
    ]
    results = []
    promotion_count = 0
    for index, hypothesis in enumerate(selected, start=1):
        _emit(progress, "compiled_specialized_hypothesis_started", index=index,
              hypothesis_id=hypothesis.get("hypothesis_id"))
        result = _resolve_one(
            root, hypothesis, history,
            promote=promote and promotion_count < max(0, maximum_promotions),
            maximum_holdouts=maximum_holdouts, progress=progress,
        )
        results.append(result)
        promotion_count += int(result.get("status") == "promoted")
        _emit(progress, "compiled_specialized_hypothesis_completed", index=index,
              hypothesis_id=hypothesis.get("hypothesis_id"), status=result.get("status"))
    return results


def _resolve_one(
    root: Path, hypothesis: dict[str, Any], history: list[dict[str, Any]], *,
    promote: bool, maximum_holdouts: int, progress=None,
) -> dict[str, Any]:
    request = capability_request(hypothesis)
    evidence_projects = {str(value) for value in hypothesis.get("evidence_refs") or []}
    counterexample_projects = {str(value) for value in hypothesis.get("counterexample_refs") or []}
    bound_projects = evidence_projects | counterexample_projects
    bound_history = [row for row in history if str(row.get("project") or "") in bound_projects]
    foundry = resolve_plugin_requests([request], bound_history)
    resolution = dict(next(iter(foundry.get("resolutions") or []), {}))
    base = {
        "hypothesis_id": hypothesis.get("hypothesis_id"),
        "candidate_type": hypothesis.get("candidate_type"),
        "required_capability": request.get("missing_capability"),
        "foundry_resolution": resolution,
    }
    if resolution.get("status") == "implementation_required":
        return {**base, "status": "implementation_required",
                "reason": "bounded_improvement_plugin_missing"}
    candidate_type = str(hypothesis.get("candidate_type") or "")
    if candidate_type == EVIDENCE_PLAN_TYPE:
        from .improvement_plugins.hypothesis_evidence_planner import run
        outcome = run({
            "compiled_hypothesis": hypothesis,
            "evidence_reports": [
                row for row in bound_history if str(row.get("project") or "") in evidence_projects
            ],
            "counterexample_reports": [
                row for row in bound_history if str(row.get("project") or "") in counterexample_projects
            ],
        })
        return {**base, **outcome}
    if candidate_type not in DIRECT_TRIAL_TYPES:
        return {**base, "status": str(resolution.get("status") or "trial_required")}
    holdouts = _independent_holdouts(hypothesis, history)[:max(1, maximum_holdouts)]
    if not holdouts:
        return {
            **base, "status": "evidence_required",
            "reason": "independent_matching_holdout_missing",
            "promotion_requested": promote,
        }
    attempts = []
    for report in holdouts:
        snapshot = capture_selection_state(root) if promote else {}
        outcome = _direct_admission(root, hypothesis, report, promote=promote, progress=progress)
        if outcome.get("status") == "promoted":
            gate = run_repository_gate(root)
            outcome["repository_regression_gate"] = gate
            if gate.get("status") != "passed":
                rollback_selection_state(root, snapshot)
                outcome.update({
                    "status": "blocked", "promotion_applied": False,
                    "reason": gate.get("reason"), "rollback_applied": True,
                })
        attempts.append({"project": report.get("project"), **outcome})
        if outcome.get("status") in {"promoted", "trial_passed"}:
            return {**base, "status": outcome["status"], "attempts": attempts}
    return {
        **base, "status": "evidence_required", "reason": (
            str(attempts[-1].get("reason")) if attempts else "direct_trial_missing"
        ), "attempts": attempts,
    }


def _independent_holdouts(
    hypothesis: dict[str, Any], history: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    evidence = {str(value) for value in hypothesis.get("evidence_refs") or []}
    policy = dict(load_project_evolution_policy().get("self_improvement") or {})
    normalization = dict(dict(policy.get("hypothesis_holdout") or {}).get(
        "signature_normalization") or {})
    matches: dict[str, dict[str, Any]] = {}
    for report in history:
        compact = compact_report(report, normalization)
        project = str(compact.get("project") or "")
        if (
            project and project not in evidence
            and compact.get("portable_signature") == hypothesis.get("portable_signature")
            and compact.get("semantic_context") == list(hypothesis.get("semantic_context") or [])
            and Path(str(report.get("project_dir") or "")).is_dir()
        ):
            matches.setdefault(project, report)
    return [matches[key] for key in sorted(matches)]


def _direct_admission(
    root: Path, hypothesis: dict[str, Any], report: dict[str, Any], *,
    promote: bool, progress=None,
) -> dict[str, Any]:
    candidate_type = str(hypothesis.get("candidate_type") or "")
    if candidate_type == "semantic_contract_profile":
        from .improvement_plugins.semantic_profile_admission import run
        plugin_id = "semantic_profile_admission"
    else:
        from .improvement_plugins.executable_adapter_admission import run
        plugin_id = "executable_adapter_admission"
    from .self_improvement_plugin_loader import enabled_improvement_plugins
    plugin = next(row for row in enabled_improvement_plugins() if row["id"] == plugin_id)
    baseline = dict(report.get("baseline") or {})
    return dict(run({
        "root": root,
        "project_dir": Path(str(report["project_dir"])),
        "failure_packet": {"selected_candidate": baseline.get("selected_extraction_candidate")},
        "diagnosis": {**dict(report.get("diagnosis") or {}),
                      "failure_class": hypothesis.get("failure_class")},
        "regression_projects": [], "promote": promote,
        "plugin_config": plugin, "progress": progress,
    }) or {})


def _emit(sink, stage: str, **details: Any) -> None:
    if sink:
        sink({"stage": stage, **details})
