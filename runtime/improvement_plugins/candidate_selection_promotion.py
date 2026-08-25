"""Promote a candidate-selection policy behind reproduction and regression gates."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from runtime.improvement_plugins.candidate_selection_refinement import (
    refine_preflight,
    refine_reproduction,
)
from runtime.improvement_plugins.candidate_selection_regression import (
    RegressionBudget,
    RegressionGateBudgetExceeded,
    evaluate_project,
    evaluate_projects,
    regression_failures,
)
from runtime.promoted_candidate_selection_policies import (
    activate_selection_policy,
    promote_selection_policy,
)
from runtime.self_improvement_iteration import (
    capture_promotion_state,
    rollback_promotion_state,
)


def promote_with_regression_gate(
    root: Path, policy: dict[str, Any], group: dict[str, Any], project_dir: Path,
    effect: dict[str, Any], regression_projects: list[Path], maximum_refinements: int,
    regression_repetitions: int = 1, regression_case_timeout: float = 60.0,
    regression_total_timeout: float = 480.0, progress=None,
) -> dict[str, Any]:
    budget = RegressionBudget(
        regression_case_timeout, regression_total_timeout,
        len(regression_projects) * (max(1, regression_repetitions) + 1), progress,
    )
    try:
        before = evaluate_projects(root, regression_projects, budget=budget)
    except RegressionGateBudgetExceeded as exc:
        return _budget_rejection(exc, rollback_applied=False)
    evidence = {
        "confirmed_projects": sorted(group["projects"]),
        "holdout_project": project_dir.name,
        "holdout_score_delta": effect["score_delta"],
    }
    candidate = dict(policy)
    refinement = None
    reproduction_refinements = 0
    regression_refinements = 0
    reproduction_history = []
    regression_history = []
    for _attempt in range(max(0, maximum_refinements) + 2):
        snapshot = capture_promotion_state(root)
        try:
            promoted = promote_selection_policy(
                root=root, policy={**candidate, "activation_state": "reproduction_trial"},
                promotion_evidence={
                    **evidence,
                    **({"regression_refinement": refinement} if refinement else {}),
                },
            )
            reproduction = holdout_reproduction_failure(root, project_dir, effect)
            reproduction_history.append({
                "target": reproduction.get("selected_candidate")
                or dict(effect.get("treatment") or {}).get("selected_extraction_candidate"),
                "score": reproduction.get("actual_score")
                or dict(effect.get("treatment") or {}).get("project_min_score"),
                "acceptance_signal": reproduction.get("actual_acceptance_signal")
                or "executable_callable",
            })
            if reproduction:
                rollback_promotion_state(root, snapshot)
                refined = refine_reproduction(candidate, effect, reproduction)
                if refined and reproduction_refinements < maximum_refinements:
                    candidate = refined
                    reproduction_refinements += 1
                    refinement = "exclude_reproduction_only_execution_cost"
                    continue
                return {
                    "applied": False, "status": "rejected",
                    "reason": "holdout_reproduction_failed",
                    "holdout_reproduction": reproduction,
                    "reproduction_history": reproduction_history,
                    "rollback_applied": True,
                }
            activated = activate_selection_policy(root, str(candidate["id"]))
            regressions = regression_failures(
                root, before, regression_repetitions,
                case_timeout_seconds=regression_case_timeout,
                total_timeout_seconds=regression_total_timeout,
                progress=progress, budget=budget,
            )
        except RegressionGateBudgetExceeded as exc:
            rollback_promotion_state(root, snapshot)
            return _budget_rejection(exc, rollback_applied=True)
        except BaseException:
            rollback_promotion_state(root, snapshot)
            raise
        if not regressions:
            return {
                "applied": promoted["status"] in {"promoted", "already_promoted"},
                **promoted, "activation": activated, "regression_gate": "passed",
                "regression_case_count": len(before),
                "reproduction_history": reproduction_history,
                "regression_history": regression_history,
                **({"refinement": refinement} if refinement else {}),
            }
        regression_history.append({
            "trigger": dict(candidate.get("preflight_trigger_requirements") or {}),
            "failures": [{
                "project": row.get("project"), "before_score": row.get("before_score"),
                "after_score": row.get("after_score"), "after_target": row.get("after_target"),
            } for row in regressions],
        })
        rollback_promotion_state(root, snapshot)
        refined = refine_preflight(candidate, effect, regressions)
        if regression_refinements >= maximum_refinements or not refined:
            return {
                "applied": False, "status": "rejected",
                "reason": "regression_gate_failed", "regressions": regressions,
                "regression_history": regression_history,
                "rollback_applied": True,
            }
        candidate = refined
        refinement = "exclude_regression_only_effects"
        regression_refinements += 1
    return {
        "applied": False, "status": "rejected", "reason": "regression_gate_failed",
        "regression_history": regression_history,
    }


def holdout_reproduction_failure(
    root: Path, project_dir: Path, effect: dict[str, Any]
) -> dict[str, Any]:
    expected = dict(effect.get("treatment") or {})
    current = evaluate_project(root, project_dir)
    expected_score = float(expected.get("project_min_score") or 0.0)
    current_score = float(current.get("project_min_score") or 0.0)
    expected_signal = str(
        dict(expected.get("downstream_evidence") or {}).get("acceptance_signal") or ""
    )
    current_signal = str(
        dict(current.get("downstream_evidence") or {}).get("acceptance_signal") or ""
    )
    reproduced = (
        current_score >= expected_score
        and _status_rank(str(current.get("status")))
        >= _status_rank(str(expected.get("status")))
        and (expected_signal != "executable_callable" or current_signal == expected_signal)
    )
    return {} if reproduced else {
        "expected_score": expected_score,
        "actual_score": current_score,
        "expected_acceptance_signal": expected_signal,
        "actual_acceptance_signal": current_signal,
        "selected_candidate": current.get("selected_extraction_candidate"),
        "selected_candidate_quality": current.get("selected_candidate_quality", {}),
    }


def _budget_rejection(
    exc: RegressionGateBudgetExceeded, *, rollback_applied: bool
) -> dict[str, Any]:
    return {
        "applied": False, "status": "rejected", "reason": exc.reason,
        "regression_budget": exc.details, "rollback_applied": rollback_applied,
    }


def _status_rank(status: str) -> int:
    return {"needs_review": 0, "blocked_ok": 1, "ok": 2}.get(status, 0)
