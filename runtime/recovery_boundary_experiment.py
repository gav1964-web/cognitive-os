"""Evidence gate for semantic recovery-boundary experiments."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


def evaluate_recovery_boundary_experiments(
    research_report: dict[str, Any],
    *,
    evidence_cases: Iterable[dict[str, Any]] = (),
    root: Path | None = None,
    write: bool = False,
) -> dict[str, Any]:
    evidence = [dict(row) for row in evidence_cases]
    experiments = [_evaluate_hypothesis(dict(row), evidence) for row in research_report.get("hypotheses", [])]
    admitted = [row["cluster"] for row in experiments if row["status"] == "admitted_for_developer_recipe"]
    report = {
        "artifact_type": "RecoveryBoundaryExperimentReport",
        "schema_version": "recovery_boundary_experiment.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "admitted" if experiments and len(admitted) == len(experiments) else "evidence_required",
        "experiments": experiments,
        "architect_gate": {
            "automatic_admission": False,
            "developer_handoff_allowed": bool(experiments) and len(admitted) == len(experiments),
            "admitted_clusters": admitted,
            "blocked_clusters": [row["cluster"] for row in experiments if row["cluster"] not in admitted],
        },
        "safety": {
            "source_changes": False,
            "network_execution": False,
            "subprocess_execution": False,
            "evidence_only": True,
        },
    }
    if write:
        if root is None:
            raise ValueError("root is required when write=True")
        out_dir = root / "artifacts" / "field_trials"
        out_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        path = out_dir / f"recovery_boundary_experiment_{stamp}.json"
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        report["report_path"] = path.as_posix()
    return report


def _evaluate_hypothesis(hypothesis: dict[str, Any], evidence: list[dict[str, Any]]) -> dict[str, Any]:
    cluster = str(hypothesis.get("cluster") or "")
    contract = dict(hypothesis.get("boundary_contract") or {})
    rows = [row for row in evidence if row.get("cluster") == cluster]
    projects = {str(row.get("project")) for row in rows if row.get("project")}
    lineages = {str(row.get("lineage")) for row in rows if row.get("lineage")}
    required_projects = int(dict(hypothesis.get("next_experiment") or {}).get("minimum_reviewed_projects") or 2)
    preserve = {str(item) for item in contract.get("preserve", [])}
    preserved = set.intersection(
        *[{str(item) for item in row.get("preserved_invariants", [])} for row in rows]
    ) if rows else set()
    checks = {
        "minimum_independent_projects": len(projects) >= required_projects,
        "minimum_independent_lineages": len(lineages) >= 2,
        "independent_holdout_present": any(row.get("holdout") is True for row in rows),
        "source_review_confirmed": bool(rows) and all(row.get("source_review_confirmed") is True for row in rows),
        "data_direction_confirmed": bool(rows) and all(row.get("data_direction_confirmed") is True for row in rows),
        "success_path_differential_passed": bool(rows) and all(row.get("success_fixture_passed") is True for row in rows),
        "failure_path_differential_passed": bool(rows) and all(row.get("failure_fixture_passed") is True for row in rows),
        "transport_or_effect_invariants_preserved": preserve <= preserved,
    }
    admitted = all(checks.values())
    return {
        "cluster": cluster,
        "status": "admitted_for_developer_recipe" if admitted else "evidence_required",
        "checks": checks,
        "reviewed_projects": sorted(projects),
        "independent_lineages": sorted(lineages),
        "required_invariants": sorted(preserve),
        "missing_invariants": sorted(preserve - preserved),
        "developer_request": {
            "status": "architect_approved",
            "pure_candidate": contract.get("pure_candidate"),
            "effect_adapter": contract.get("effect_adapter"),
        } if admitted else None,
    }
