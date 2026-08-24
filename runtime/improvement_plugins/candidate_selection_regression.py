"""Repeated regression evaluation for candidate-selection promotion."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def evaluate_projects(root: Path, projects: list[Path]) -> list[dict[str, Any]]:
    return [
        {"project": path.name, "project_dir": path, "result": evaluate_project(root, path)}
        for path in projects
    ]


def regression_failures(
    root: Path, before: list[dict[str, Any]], repetitions: int,
) -> list[dict[str, Any]]:
    failures = []
    for row in before:
        prior = dict(row["result"])
        currents = [
            evaluate_project(root, Path(row["project_dir"]))
            for _ in range(max(1, repetitions))
        ]
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


def evaluate_project(root: Path, project: Path) -> dict[str, Any]:
    """Use the same execution-feedback route as the outer corpus gate."""
    from runtime.role_foundation_field_trial import _run_isolated_case

    return _run_isolated_case(
        root=root,
        project_dir=project,
        write=True,
        executable_acceptance=True,
    )


def _regressed(prior: dict[str, Any], current: dict[str, Any]) -> bool:
    return (
        float(current.get("project_min_score") or 0) < float(prior.get("project_min_score") or 0)
        or _status_rank(str(current.get("status"))) < _status_rank(str(prior.get("status")))
    )


def _status_rank(status: str) -> int:
    return {"needs_review": 0, "blocked_ok": 1, "ok": 2}.get(status, 0)
