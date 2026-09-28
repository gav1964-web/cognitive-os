"""Build an evidence-backed project evolution report from field trials."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime.project_evolution_policy import evaluate_project_evolution


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--baseline-report", required=True)
    parser.add_argument("--current-report", required=True)
    parser.add_argument("--holdout-report")
    parser.add_argument("--change-type", action="append", default=[])
    parser.add_argument("--evidence", action="append", default=[])
    parser.add_argument("--anti-pattern", action="append", default=[])
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    report = build_project_evolution_report(
        root=root,
        baseline_report=Path(args.baseline_report),
        current_report=Path(args.current_report),
        change_types=args.change_type,
        evidence=args.evidence,
        anti_patterns=args.anti_pattern,
        holdout_report=Path(args.holdout_report) if args.holdout_report else None,
    )
    if args.write:
        report.update(write_report(root, report))
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] == "ok" else 1


def build_project_evolution_report(
    *,
    root: Path,
    baseline_report: Path,
    current_report: Path,
    change_types: list[str],
    evidence: list[str],
    anti_patterns: list[str],
    holdout_report: Path | None = None,
) -> dict[str, Any]:
    baseline = _read_report(root, baseline_report)
    current = _read_report(root, current_report)
    holdout = _read_report(root, holdout_report) if holdout_report else None
    field_delta = _acceptance_callable(current) - _acceptance_callable(baseline)
    holdout_summary = _holdout_summary(baseline, current, holdout)
    inferred_evidence = _inferred_evidence(baseline, current, holdout_summary)
    change = {
        "change_types": list(change_types),
        "evidence": sorted(set(evidence) | inferred_evidence),
        "anti_patterns": list(anti_patterns),
        "field_callable_delta": field_delta,
    }
    evolution = evaluate_project_evolution(change)
    return {
        "artifact_type": "ProjectEvolutionRunReport",
        "status": evolution["status"],
        "generated_at": _now(),
        "baseline_report": _display_path(root, baseline_report),
        "current_report": _display_path(root, current_report),
        "holdout_report": _display_path(root, holdout_report) if holdout_report else None,
        "field_callable_delta": field_delta,
        "independent_holdout": holdout_summary,
        "change": change,
        "evolution": evolution,
        "summary": {
            "baseline_acceptance_callable": _acceptance_callable(baseline),
            "current_acceptance_callable": _acceptance_callable(current),
            "baseline_project_count": int(baseline.get("project_count") or 0),
            "current_project_count": int(current.get("project_count") or 0),
        },
    }


def write_report(root: Path, report: dict[str, Any]) -> dict[str, str]:
    report_dir = root / "artifacts" / "project_evolution"
    report_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = report_dir / f"project_evolution_{stamp}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"report_path": path.as_posix()}


def _read_report(root: Path, path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    source = path if path.is_absolute() else root / path
    return json.loads(source.read_text(encoding="utf-8"))


def _inferred_evidence(baseline: dict[str, Any], current: dict[str, Any], holdout_summary: dict[str, Any]) -> set[str]:
    evidence: set[str] = set()
    if baseline.get("artifact_type") == "GitHubExecutorProbe" and current.get("artifact_type") == "GitHubExecutorProbe":
        evidence.add("field_report")
    if int(dict(current.get("summary") or {}).get("source_code_changes") or 0) == 0:
        evidence.add("no_source_changes")
    if holdout_summary.get("status") == "passed":
        evidence.add("independent_holdout")
    return evidence


def _holdout_summary(baseline: dict[str, Any], current: dict[str, Any], holdout: dict[str, Any] | None) -> dict[str, Any]:
    candidate = holdout or current
    baseline_projects = _project_names(baseline)
    candidate_projects = _project_names(candidate)
    overlap = sorted(baseline_projects & candidate_projects)
    source_changes = int(dict(candidate.get("summary") or {}).get("source_code_changes") or 0)
    artifact_ok = candidate.get("artifact_type") == "GitHubExecutorProbe"
    run_ok = candidate.get("status") == "ok"
    project_count = int(candidate.get("project_count") or len(candidate_projects))
    passed = artifact_ok and run_ok and bool(candidate_projects) and not overlap and source_changes == 0
    return {
        "status": "passed" if passed else "not_independent",
        "run_status": candidate.get("status"),
        "project_count": project_count,
        "overlap_count": len(overlap),
        "overlap_projects": overlap[:10],
        "source_code_changes": source_changes,
    }


def _project_names(report: dict[str, Any]) -> set[str]:
    return {
        str(case.get("project"))
        for case in list(report.get("cases") or [])
        if isinstance(case, dict) and case.get("project")
    }


def _acceptance_callable(report: dict[str, Any]) -> int:
    return int(dict(report.get("summary") or {}).get("acceptance_callable") or 0)


def _display_path(root: Path, path: Path | None) -> str:
    if path is None:
        return ""
    source = path if path.is_absolute() else root / path
    try:
        return source.resolve().relative_to(root).as_posix()
    except ValueError:
        return source.as_posix()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


if __name__ == "__main__":
    raise SystemExit(main())
