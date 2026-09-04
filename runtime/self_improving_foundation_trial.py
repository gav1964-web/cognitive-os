"""Corpus-driven self-improvement orchestration for foundation roles."""

from __future__ import annotations

import json
import inspect
from pathlib import Path
from typing import Any, Callable

from .knowledge_admission import capability_gap_report, load_kb_candidates
from .project_evolution_policy import load_project_evolution_policy
from .role_foundation_field_trial import run_role_foundation_field_trial
from .self_improvement_capability_request import capability_development_requests
from .self_improvement_iteration import (
    assess_iteration,
    capture_promotion_state,
    changed_promotion_paths,
    rollback_promotion_state,
    snapshot_digest,
)
from .self_improvement_hypothesis_validation import HoldoutDiscoverer, run_hypothesis_validation
from .self_improvement_engine_fingerprint import improvement_engine_fingerprint
from .self_improvement_training import probe_project, train_on_project
from .self_development_change import build_capability_change_dossier
from .self_improving_foundation_trial_io import write_checkpoint as _write_checkpoint
from .self_improving_foundation_trial_io import write_report as _write_report


Trainer = Callable[..., dict[str, Any]]
ProgressSink = Callable[[dict[str, Any]], None]


def run_self_improving_foundation_trial(
    *,
    root: Path,
    project_roots: list[Path],
    limit: int = 0,
    target_score: float = 9.7,
    max_training_projects: int = 3,
    max_iterations: int | None = None,
    regression_case_count: int = 3,
    promote_config: bool | None = None,
    write: bool = True,
    executable_acceptance: bool = True,
    _trainer: Trainer = train_on_project,
    _holdout_discoverer: HoldoutDiscoverer | None = None,
    _progress: ProgressSink | None = None,
) -> dict[str, Any]:
    """Let Cognitive OS train, verify, promote, and roll back until convergence."""
    policy = dict(load_project_evolution_policy().get("self_improvement") or {})
    training_priority_policy = dict(policy.get("training_priority") or {})
    case_timeout = float(policy.get("maximum_field_trial_case_seconds") or 0.0)
    iteration_limit = max(1, int(max_iterations or policy.get("max_training_iterations") or 1))
    _emit(_progress, "baseline_started")
    baseline = _measure(root, project_roots, limit, write, target_score, executable_acceptance, _progress, case_timeout)
    initial_cases = list(baseline.get("cases") or [])
    initial_failures = [case for case in initial_cases if _requires_training(case, target_score)]
    _emit(_progress, "baseline_completed", failure_count=len(initial_failures))
    verification = baseline
    training: list[dict[str, Any]] = []
    iterations: list[dict[str, Any]] = []
    stop_reason = ""
    maximum_regression_cases = 0
    engine_fingerprint = improvement_engine_fingerprint(root)
    attempted_projects = _prior_attempted_projects(root, initial_cases, engine_fingerprint)
    for iteration in range(1, iteration_limit + 1):
        cases = list(verification.get("cases") or [])
        failures = sorted(
            (
                case for case in cases
                if _trainable_failure(case, target_score)
                and str(case.get("project") or "") not in attempted_projects
            ),
            key=lambda case: _training_priority(case, training_priority_policy),
        )[:max(0, max_training_projects)]
        if not failures:
            if any(_requires_training(case, target_score) for case in cases):
                stop_reason = "autonomous_evidence_exhausted_without_promotion"
            break
        regression_projects = _regression_projects(cases, target_score, regression_case_count)
        maximum_regression_cases = max(maximum_regression_cases, len(regression_projects))
        snapshot = capture_promotion_state(root)
        round_training: list[dict[str, Any]] = []
        for index, case in enumerate(failures, start=1):
            _emit(
                _progress, "training_started", iteration=iteration,
                index=index, project=case["project"],
            )
            trainer_kwargs = dict(
                root=root,
                project_dir=Path(str(case["project_dir"])),
                target_score=target_score,
                regression_projects=[
                    path for path in regression_projects
                    if path != Path(str(case["project_dir"]))
                ],
                promote_config=promote_config,
                write=write,
            )
            if "progress" in inspect.signature(_trainer).parameters:
                trainer_kwargs["progress"] = _progress
            report = _trainer(**trainer_kwargs)
            round_training.append(report); training.append(report)
            if write:
                _write_checkpoint(root, baseline, training, target_score)
            _emit(
                _progress, "training_completed", iteration=iteration,
                index=index, project=case["project"], status=report.get("status"),
            )
        holdout = {"status": "not_requested", "training": [], "promotion_count": 0}
        staged = any(_staged_learning(report) for report in round_training)
        if _holdout_discoverer and staged and not any(_promotion_count(row) for row in round_training):
            _emit(_progress, "hypothesis_validation_started", iteration=iteration)
            holdout = run_hypothesis_validation(
                root=root, training=round_training, discover=_holdout_discoverer,
                trainer=_trainer, target_score=target_score,
                regression_projects=regression_projects, promote_config=promote_config,
                write=write, policy=policy,
                probe=probe_project if _trainer is train_on_project else None,
                progress=_progress,
            )
            holdout_training = list(holdout.get("training") or [])
            training.extend(holdout_training)
            if write and holdout_training:
                _write_checkpoint(root, baseline, training, target_score)
            _emit(
                _progress, "hypothesis_validation_completed", iteration=iteration,
                status=holdout.get("status"), decision=holdout.get("decision"),
            )
        changed = changed_promotion_paths(root, snapshot)
        promoted = (
            bool(changed) or any(_promotion_count(row) for row in round_training)
            or int(holdout.get("promotion_count") or 0) > 0
        )
        if promoted:
            _emit(_progress, "verification_started", iteration=iteration)
            candidate = _measure(
                root, project_roots, limit, write, target_score, executable_acceptance, _progress, case_timeout
            )
        else:
            _emit(
                _progress, "verification_skipped", iteration=iteration,
                reason="active_promotion_missing",
            )
            candidate = verification
        assessment = assess_iteration(verification, candidate, target_score=target_score)
        rollback = {"applied": False, "paths": []}
        if changed and assessment["status"] != "accepted":
            rollback = {"applied": True, "paths": rollback_promotion_state(root, snapshot)}
            candidate = _measure(
                root, project_roots, limit, write, target_score, executable_acceptance, _progress, case_timeout
            )
        iterations.append({
            "iteration": iteration,
            "snapshot_sha256": snapshot_digest(snapshot),
            "training": round_training,
            "hypothesis_validation": holdout,
            "assessment": assessment,
            "promoted": promoted,
            "changed_paths": changed,
            "rollback": rollback,
            "verification": candidate,
        })
        verification = candidate
        if verification.get("status") == "ok":
            break
        if not promoted:
            attempted_projects.update(str(case.get("project") or "") for case in failures)
            requests = capability_development_requests(
                root,
                training,
                minimum_projects=int(policy.get("minimum_capability_request_projects") or 3),
            )
            if requests:
                stop_reason = "missing_registered_improvement_capability"; break
            staged = {
                str(case.get("project") or "")
                for case, row in zip(failures, round_training)
                if _staged_learning(row)
            }
            if staged:
                continue
            stop_reason = "no_safe_autonomous_promotion"; break
        if assessment["status"] != "accepted":
            stop_reason = "promotion_failed_corpus_gate"
            break
        attempted_projects.clear()
    capability_requests = [
        *capability_development_requests(
            root, training,
            minimum_projects=int(policy.get("minimum_capability_request_projects") or 3),
        ),
        *_resource_capability_requests(list(verification.get("cases") or [])),
    ]
    shadow_dossiers = [
        build_capability_change_dossier(
            request,
            evaluator_fingerprint=engine_fingerprint,
        )
        for request in capability_requests
    ]
    remaining_unattempted = any(
        _trainable_failure(case, target_score)
        and str(case.get("project") or "") not in attempted_projects
        for case in list(verification.get("cases") or [])
    )
    if capability_requests and verification.get("status") != "ok":
        stop_reason = "missing_registered_improvement_capability"
    elif verification.get("status") != "ok" and not stop_reason:
        stop_reason = (
            "autonomous_iteration_budget_exhausted"
            if remaining_unattempted else "autonomous_evidence_exhausted_without_promotion"
        )
    report = {
        "artifact_type": "SelfImprovingFoundationFieldTrialReport",
        "status": _status(verification, stop_reason),
        "target_score": target_score,
        "improvement_engine_fingerprint": engine_fingerprint,
        "baseline": baseline,
        "training": training,
        "iterations": iterations,
        "verification": verification,
        "critical_intervention": {
            "required": bool(stop_reason),
            "reason": stop_reason or None,
            "authority": "external_engineer" if stop_reason else None,
            "allowed_scope": "repair_self_improvement_capability_only" if stop_reason else None,
        },
        "capability_gaps": capability_gap_report(load_kb_candidates(root=root)),
        "capability_development_requests": capability_requests,
        "self_development_shadow_dossiers": shadow_dossiers,
        "summary": {
            "eligible_failure_count": len(initial_failures),
            "resource_blocked_project_count": len(_resource_blocked_projects(initial_cases)),
            "training_project_count": len(training),
            "iteration_count": len(iterations),
            "promotion_count": sum(bool(row.get("promoted")) for row in iterations),
            "rollback_count": sum(bool(dict(row.get("rollback") or {}).get("applied")) for row in iterations),
            "candidate_improvement_count": sum(
                report.get("status") == "candidate_improvement_confirmed" for report in training
            ),
            "target_reached_count": sum(
                bool(dict(report.get("outcome") or {}).get("target_reached")) for report in training
            ),
            "regression_case_count": maximum_regression_cases,
            "hypothesis_holdout_project_count": sum(
                int(dict(row.get("hypothesis_validation") or {}).get("discovered_project_count") or 0)
                for row in iterations
            ),
        },
        "invariants": {
            "field_trial_is_measurement_only": True,
            "source_project_changes_allowed": False,
            "active_kb_promotion_mode": "gated_improvement_plugins",
            "manual_project_repair_allowed": False,
            "critical_intervention_repairs_loop_only": True,
            "self_development_dossiers_are_shadow_only": True,
            "config_promotion_mode": "plugin_policy" if promote_config is None else "enabled" if promote_config else "disabled",
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


def _trainable_failure(case: dict[str, Any], target_score: float) -> bool:
    return _requires_training(case, target_score) and case.get("blocker") != "field_trial_case_timeout"


def _resource_blocked_projects(cases: list[dict[str, Any]]) -> list[str]:
    return sorted({
        str(case.get("project") or "") for case in cases
        if case.get("blocker") == "field_trial_case_timeout"
    })


def _resource_capability_requests(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    projects = _resource_blocked_projects(cases)
    if not projects:
        return []
    return [{
        "artifact_type": "CapabilityDevelopmentRequest",
        "request_id": "cdr_bounded_foundation_analysis_optimization",
        "status": "implementation_required",
        "missing_capability": "bounded_foundation_analysis_optimization",
        "observed_projects": projects,
        "intervention_scope": "optimize_or_partition_foundation_analysis_only",
        "forbidden": ["manual_project_repair", "evaluation_threshold_change", "timeout_increase"],
    }]


def _training_priority(
    case: dict[str, Any], policy: dict[str, Any] | None = None,
) -> tuple[int, float, str]:
    priority = dict(policy or {})
    downstream = dict(case.get("downstream_evidence") or {})
    actionable = (
        str(downstream.get("acceptance_signal") or "")
        in set(priority.get("actionable_acceptance_signals") or [])
        or str(downstream.get("status") or "")
        in set(priority.get("actionable_downstream_statuses") or [])
    )
    score = float(case.get("project_min_score") or 0.0)
    if case.get("status") == "blocked_ok":
        score = min(score, 7.0)
    elif case.get("status") != "ok":
        score = min(score, 5.0)
    return int(not actionable), score, str(case.get("project") or "")


def _prior_attempted_projects(
    root: Path, cases: list[dict[str, Any]], engine_fingerprint: str
) -> set[str]:
    directory = root / "artifacts" / "self_improvement"
    current = {str(row.get("project") or "") for row in cases}
    attempted: set[str] = set()
    for path in sorted(directory.glob("self_improving_foundation_trial_*.json"), reverse=True):
        try:
            report = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if report.get("status") != "critical_intervention_required":
            continue
        if report.get("improvement_engine_fingerprint") != engine_fingerprint:
            continue
        prior = {str(row.get("project") or "") for row in report.get("baseline", {}).get("cases", [])}
        if current == prior:
            attempted.update(str(row.get("project") or "") for row in report.get("training", []))
    return attempted


def _regression_projects(
    cases: list[dict[str, Any]], target_score: float, count: int
) -> list[Path]:
    stable = [
        case for case in cases
        if case.get("status") == "ok" and float(case.get("project_min_score") or 0.0) >= target_score
    ]
    stable.sort(key=lambda case: (-float(case.get("project_min_score") or 0.0), str(case.get("project") or "")))
    return [Path(str(case["project_dir"])) for case in stable[:max(0, count)]]


def _status(verification: dict[str, Any], stop_reason: str) -> str:
    if verification.get("status") == "ok":
        return "target_verified"
    return "critical_intervention_required" if stop_reason else "autonomous_improvement_in_progress"


def _promotion_count(report: dict[str, Any]) -> int:
    cycle = dict(report.get("improvement_plugin_cycle") or {})
    post = dict(report.get("post_training_admission") or {})
    return int(cycle.get("promotion_count") or 0) + int(post.get("promotion_count") or 0)


def _staged_learning(report: dict[str, Any]) -> bool:
    return bool(report.get("knowledge_candidate_path"))


def _measure(
    root: Path, project_roots: list[Path], limit: int, write: bool,
    target_score: float, executable_acceptance: bool, progress: ProgressSink | None,
    case_timeout_seconds: float,
) -> dict[str, Any]:
    return run_role_foundation_field_trial(
        root=root, project_roots=project_roots, limit=limit, write=write,
        target_score=target_score, executable_acceptance=executable_acceptance, progress=progress,
        case_timeout_seconds=case_timeout_seconds,
    )


def _emit(sink: ProgressSink | None, stage: str, **details: Any) -> None:
    if sink:
        sink({"stage": stage, **details})
