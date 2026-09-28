"""Build compact reusable evidence clusters from prior self-improvement reports."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .self_improvement_signatures import (
    normalize_failure_class,
    portable_failure_signature,
    semantic_context,
)


def load_compiler_reports(root: Path, *, limit: int) -> list[dict[str, Any]]:
    directory = root / "artifacts" / "self_improvement"
    paths = sorted(directory.glob("self_improvement_*.json"), reverse=True)[:max(0, limit)]
    reports = []
    for path in paths:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict) and payload.get("diagnosis"):
            reports.append(payload)
    return reports


def build_evidence_cluster(
    current: dict[str, Any], history: list[dict[str, Any]], *,
    normalization: dict[str, Any], maximum_cases: int, maximum_counterexamples: int,
) -> dict[str, Any]:
    anchor = compact_report(current, normalization)
    rows = [compact_report(report, normalization) for report in history]
    rows = [row for row in rows if row.get("project") and row["project"] != anchor.get("project")]
    positives = _unique_projects([
        anchor,
        *[
            row for row in rows
            if row["portable_signature"] == anchor["portable_signature"]
            and row["semantic_context"] == anchor["semantic_context"]
        ],
    ])[:max(1, maximum_cases)]
    counterexamples = _unique_projects([
        row for row in rows
        if row["failure_class"] == anchor["failure_class"]
        and row["portable_signature"] != anchor["portable_signature"]
    ])[:max(0, maximum_counterexamples)]
    return {
        "cluster_key": "|".join([
            anchor["portable_signature"], ",".join(anchor["semantic_context"]) or "context_free",
        ]),
        "failure_class": anchor["failure_class"],
        "portable_signature": anchor["portable_signature"],
        "semantic_context": anchor["semantic_context"],
        "positive_cases": positives,
        "counterexamples": counterexamples,
        "observed_project_count": len(positives),
    }


def compact_report(report: dict[str, Any], normalization: dict[str, Any]) -> dict[str, Any]:
    diagnosis = dict(report.get("diagnosis") or {})
    baseline = dict(report.get("baseline") or {})
    trained = dict(report.get("trained_attempt") or baseline)
    outcome = dict(report.get("outcome") or {})
    plugin_attempts = [
        dict(row) for cycle_name in ("improvement_plugin_cycle", "post_training_admission")
        for row in list(dict(report.get(cycle_name) or {}).get("attempts") or [])
        if isinstance(row, dict)
    ]
    failure_class = normalize_failure_class(
        str(diagnosis.get("failure_class") or "unknown"), normalization,
    )
    return {
        "project": str(report.get("project") or ""),
        "failure_class": failure_class,
        "portable_signature": portable_failure_signature(report, normalization),
        "semantic_context": semantic_context(report),
        "before_score": baseline.get("project_min_score"),
        "after_score": trained.get("project_min_score"),
        "score_delta": outcome.get("score_delta"),
        "outcome_status": outcome.get("status") or report.get("status"),
        "selected_candidate": baseline.get("selected_extraction_candidate"),
        "successful_candidate": trained.get("selected_extraction_candidate"),
        "executable_failure_family": next((
            value.split(":", 1)[1] for value in semantic_context(report)
            if value.startswith("executable_failure:")
        ), ""),
        "plugin_outcomes": [
            {"plugin_id": row.get("plugin_id"), "status": row.get("status"), "reason": row.get("reason")}
            for row in plugin_attempts
        ],
    }


def _unique_projects(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    seen = set()
    for row in rows:
        project = str(row.get("project") or "")
        if not project or project in seen:
            continue
        seen.add(project); result.append(row)
    return result
