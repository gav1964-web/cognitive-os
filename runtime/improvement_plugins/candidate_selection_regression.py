"""Repeated regression evaluation for candidate-selection promotion."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable


ProgressSink = Callable[[dict[str, Any]], None]


class RegressionGateBudgetExceeded(RuntimeError):
    def __init__(self, reason: str, details: dict[str, Any]):
        super().__init__(reason)
        self.reason = reason
        self.details = details


@dataclass
class RegressionBudget:
    case_timeout_seconds: float = 60.0
    total_timeout_seconds: float = 480.0
    total_evaluations: int = 0
    progress: ProgressSink | None = None
    started: float = field(default_factory=time.monotonic)
    completed: int = 0

    def remaining(self) -> float:
        return self.total_timeout_seconds - (time.monotonic() - self.started)


def evaluate_projects(
    root: Path, projects: list[Path], *, budget: RegressionBudget | None = None,
) -> list[dict[str, Any]]:
    return [{
        "project": path.name, "project_dir": path,
        "result": _bounded_evaluation(root, path, budget, "regression_baseline", 1, 1),
    } for path in projects]


def regression_failures(
    root: Path, before: list[dict[str, Any]], repetitions: int, *,
    case_timeout_seconds: float = 60.0, total_timeout_seconds: float = 480.0,
    progress: ProgressSink | None = None,
    budget: RegressionBudget | None = None,
) -> list[dict[str, Any]]:
    failures = []
    repeat_count = max(1, repetitions)
    budget = budget or RegressionBudget(
        case_timeout_seconds, total_timeout_seconds,
        len(before) * repeat_count, progress,
    )
    for row in before:
        prior = dict(row["result"])
        currents = []
        for repetition in range(1, repeat_count + 1):
            current = _bounded_evaluation(
                root, Path(row["project_dir"]), budget,
                "regression_case", repetition, repeat_count,
            )
            currents.append(current)
        failed = [current for current in currents if _regressed(prior, current)]
        if failed:
            worst = min(failed, key=lambda value: float(value.get("project_min_score") or 0))
            failures.append({
                "project": row["project"],
                "before_score": prior.get("project_min_score"),
                "after_score": worst.get("project_min_score"),
                "after_target": worst.get("selected_extraction_candidate"),
                "failed_repetition_count": len(failed),
                "selected_candidate_quality": prior.get("selected_candidate_quality", {}),
                "after_selected_candidate_quality": worst.get("selected_candidate_quality", {}),
            })
    return failures


def evaluate_project(
    root: Path, project: Path, *, timeout_seconds: float = 0.0,
) -> dict[str, Any]:
    """Use the same execution-feedback route as the outer corpus gate."""
    from runtime.role_foundation_case_runner import run_bounded_foundation_case
    from runtime.role_foundation_field_trial import _run_isolated_case

    return run_bounded_foundation_case(
        _run_isolated_case, {
            "root": root, "project_dir": project, "write": True,
            "executable_acceptance": True,
        }, timeout_seconds,
    )


def _bounded_evaluation(
    root: Path, project: Path, budget: RegressionBudget | None,
    stage: str, repetition: int, repetitions: int,
) -> dict[str, Any]:
    if budget is None:
        return evaluate_project(root, project)
    remaining = budget.remaining()
    if budget.total_timeout_seconds > 0 and remaining <= 0:
        raise _budget_error(budget, "regression_gate_budget_exceeded", project)
    timeout = budget.case_timeout_seconds
    if budget.total_timeout_seconds > 0:
        timeout = min(timeout, remaining) if timeout > 0 else remaining
    row = {"project": project.name}
    _emit(budget.progress, f"{stage}_started", row, repetition, repetitions, budget.completed, budget.total_evaluations)
    result = evaluate_project(root, project, timeout_seconds=max(0.001, timeout))
    budget.completed += 1
    _emit(
        budget.progress, f"{stage}_completed", row, repetition, repetitions,
        budget.completed, budget.total_evaluations, status=result.get("status"),
        blocker=result.get("blocker"),
    )
    if result.get("blocker") == "field_trial_case_timeout":
        raise _budget_error(budget, "regression_case_timeout", project)
    return result


def _budget_error(
    budget: RegressionBudget, reason: str, project: Path,
) -> RegressionGateBudgetExceeded:
    return RegressionGateBudgetExceeded(reason, {
        "project": project.name, "completed_evaluations": budget.completed,
        "total_evaluations": budget.total_evaluations,
        "elapsed_seconds": round(time.monotonic() - budget.started, 3),
    })


def _emit(
    progress: ProgressSink | None, stage: str, row: dict[str, Any],
    repetition: int, repetitions: int, completed: int, total: int, **details: Any,
) -> None:
    if progress:
        progress({
            "stage": stage, "project": row["project"],
            "repetition": repetition, "repetitions": repetitions,
            "completed": completed, "total": total, **details,
        })


def _regressed(prior: dict[str, Any], current: dict[str, Any]) -> bool:
    return (
        float(current.get("project_min_score") or 0) < float(prior.get("project_min_score") or 0)
        or _status_rank(str(current.get("status"))) < _status_rank(str(prior.get("status")))
    )


def _status_rank(status: str) -> int:
    return {"needs_review": 0, "blocked_ok": 1, "ok": 2}.get(status, 0)
