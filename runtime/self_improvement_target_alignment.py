"""Align structural retrieval evidence with an evaluation-only role probe."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable


def probe_for_plan(
    probe: Callable[..., dict[str, Any]] | None,
    root: Path,
    project: Path,
    target_score: float,
    plan: dict[str, Any],
) -> dict[str, Any] | None:
    if probe is None:
        return None
    target = str(dict(plan.get("retrieval_targets") or {}).get(project.name) or "")
    kwargs: dict[str, Any] = {
        "root": root, "project_dir": project, "target_score": target_score,
    }
    if target:
        kwargs["evaluation_target"] = target
    result = probe(**kwargs)
    recovery = dict(plan.get("recovery_targets") or {}).get(project.name) or []
    recovery_candidates = (
        [str(value) for value in recovery if value]
        if isinstance(recovery, list) else [str(recovery)]
    )
    if recovery_candidates:
        result.setdefault("baseline", {})
        result["baseline"]["retrieval_recovery_candidates"] = recovery_candidates[:4]
    if target:
        selected = str(
            dict(result.get("baseline") or {}).get("selected_extraction_candidate") or ""
        )
        result["retrieval_alignment"] = {
            "mode": "evaluation_only",
            "target": target,
            "selected_target": selected,
            "aligned": selected == target,
        }
    return result


def retrieval_targets(report: dict[str, Any]) -> dict[str, str]:
    """Return the best frozen structural sample per shortlisted project."""
    selected = set(report.get("selected_projects") or [])
    targets: dict[str, str] = {}
    for row in report.get("projects") or []:
        project = str(row.get("project") or "")
        samples = list(
            row.get("contextual_evidence_samples")
            or row.get("evidence_samples") or []
        )
        best = max(samples, key=lambda sample: int(sample.get("score") or 0), default={})
        if project in selected and best.get("source"):
            targets[project] = str(best["source"])
    return targets


def recovery_targets(report: dict[str, Any]) -> dict[str, list[str]]:
    """Return bounded structural recovery candidates without granting admission authority."""
    selected = set(report.get("selected_projects") or [])
    targets = {}
    for row in report.get("projects") or []:
        project = str(row.get("project") or "")
        samples = list(row.get("recovery_evidence_samples") or [])
        sources = [str(sample.get("source") or "") for sample in samples]
        if project in selected and any(sources):
            targets[project] = [source for source in sources if source][:4]
    return targets


def remember_retrieval_target(
    plan: dict[str, Any], probe_summary: dict[str, Any], project: Path
) -> None:
    target = str(
        dict(probe_summary.get("retrieval_alignment") or {}).get("target") or ""
    )
    if target:
        plan.setdefault("retrieval_targets", {})[project.name] = target
