"""Corpus-driven self-improvement orchestration for foundation roles."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .role_foundation_field_trial import run_role_foundation_field_trial
from .self_improvement_training import train_on_project


Trainer = Callable[..., dict[str, Any]]
ProgressSink = Callable[[dict[str, Any]], None]


def run_self_improving_foundation_trial(
    *,
    root: Path,
    project_roots: list[Path],
    limit: int = 0,
    target_score: float = 9.7,
    max_training_projects: int = 3,
    regression_case_count: int = 3,
    promote_config: bool = False,
    write: bool = True,
    executable_acceptance: bool = True,
    _trainer: Trainer = train_on_project,
    _progress: ProgressSink | None = None,
) -> dict[str, Any]:
    """Measure a corpus, train on its weakest cases, then verify the corpus again."""
    _emit(_progress, "baseline_started")
    baseline = run_role_foundation_field_trial(
        root=root,
        project_roots=project_roots,
        limit=limit,
        write=write,
        target_score=target_score,
        executable_acceptance=executable_acceptance,
    )
    cases = list(baseline.get("cases") or [])
    failures = sorted(
        (case for case in cases if _requires_training(case, target_score)),
        key=_training_priority,
    )[:max(0, max_training_projects)]
    regression_projects = _regression_projects(cases, target_score, regression_case_count)
    _emit(_progress, "baseline_completed", failure_count=len(failures))
    training = []
    for index, case in enumerate(failures, start=1):
        _emit(_progress, "training_started", index=index, project=case["project"])
        training.append(_trainer(
            root=root,
            project_dir=Path(str(case["project_dir"])),
            target_score=target_score,
            regression_projects=[path for path in regression_projects if path != Path(str(case["project_dir"]))],
            promote_config=promote_config,
            write=write,
        ))
        _emit(
            _progress, "training_completed", index=index, project=case["project"],
            status=training[-1].get("status"),
        )
    _emit(_progress, "verification_started")
    verification = run_role_foundation_field_trial(
        root=root,
        project_roots=project_roots,
        limit=limit,
        write=write,
        target_score=target_score,
        executable_acceptance=executable_acceptance,
    ) if training else baseline
    report = {
        "artifact_type": "SelfImprovingFoundationFieldTrialReport",
        "status": _status(verification, training),
        "target_score": target_score,
        "baseline": baseline,
        "training": training,
        "verification": verification,
        "summary": {
            "eligible_failure_count": sum(_requires_training(case, target_score) for case in cases),
            "training_project_count": len(training),
            "confirmed_improvement_count": sum(
                report.get("status") == "confirmed_improvement" for report in training
            ),
            "target_reached_count": sum(
                bool(dict(report.get("outcome") or {}).get("target_reached")) for report in training
            ),
            "regression_case_count": len(regression_projects),
        },
        "invariants": {
            "field_trial_is_measurement_only": True,
            "source_project_changes_allowed": False,
            "active_kb_auto_promotion": False,
            "config_promotion_requested": promote_config,
        },
    }
    if write:
        report["report_path"] = _write_report(root, report).as_posix()
    _emit(_progress, "completed", status=report["status"])
    return report


def _requires_training(case: dict[str, Any], target_score: float) -> bool:
    return (
        case.get("status") != "out_of_scope"
        and (case.get("status") != "ok" or float(case.get("project_min_score") or 0.0) < target_score)
    )


def _training_priority(case: dict[str, Any]) -> tuple[float, str]:
    score = float(case.get("project_min_score") or 0.0)
    if case.get("status") == "blocked_ok":
        score = min(score, 7.0)
    elif case.get("status") != "ok":
        score = min(score, 5.0)
    return score, str(case.get("project") or "")


def _regression_projects(
    cases: list[dict[str, Any]], target_score: float, count: int
) -> list[Path]:
    stable = [
        case for case in cases
        if case.get("status") == "ok" and float(case.get("project_min_score") or 0.0) >= target_score
    ]
    stable.sort(key=lambda case: (-float(case.get("project_min_score") or 0.0), str(case.get("project") or "")))
    return [Path(str(case["project_dir"])) for case in stable[:max(0, count)]]


def _status(verification: dict[str, Any], training: list[dict[str, Any]]) -> str:
    if verification.get("status") == "ok":
        return "target_verified"
    if any(report.get("status") == "confirmed_improvement" for report in training):
        return "improvement_candidates_staged"
    return "needs_work"


def _emit(sink: ProgressSink | None, stage: str, **details: Any) -> None:
    if sink:
        sink({"stage": stage, **details})


def _write_report(root: Path, report: dict[str, Any]) -> Path:
    directory = root / "artifacts" / "self_improvement"
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = directory / f"self_improving_foundation_trial_{stamp}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path
