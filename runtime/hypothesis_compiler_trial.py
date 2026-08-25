"""Replay compiled hypotheses through existing admission and rollback gates."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .hypothesis_compiler_evidence import compact_report, load_compiler_reports
from .hypothesis_compiler_specialized_trial import run_specialized_trials
from .hypothesis_compiler_repository_gate import (
    capture_selection_state, reject_promoted_result,
    rollback_selection_state, run_repository_gate,
)
from .project_evolution_policy import load_project_evolution_policy
from .self_improvement_hypothesis_compiler import load_hypothesis_compiler_config
from .self_improvement_plugin_loader import enabled_improvement_plugins


Admission = Callable[[dict[str, Any]], dict[str, Any]]


def run_compiled_hypothesis_trials(
    *, root: Path, compilation_path: Path, promote: bool = False,
    maximum_promotions: int = 1, maximum_holdouts_per_hypothesis: int = 3,
    case_timeout_seconds: float = 30.0, total_timeout_seconds: float = 180.0,
    hypothesis_ids: set[str] | None = None,
    candidate_types: set[str] | None = None,
    timeout_retry_multipliers: tuple[float, ...] | None = None,
    retry_quarantined: bool = False,
    repository_verifier=None,
    write: bool = True, admission: Admission | None = None, progress=None,
) -> dict[str, Any]:
    payload = json.loads(compilation_path.read_text(encoding="utf-8"))
    all_hypotheses = [dict(row) for row in payload.get("hypotheses") or []]
    hypotheses = [
        dict(row) for row in payload.get("hypotheses") or []
        if dict(row).get("candidate_type") == "candidate_selection_rule"
        and (candidate_types is None or "candidate_selection_rule" in candidate_types)
        and (hypothesis_ids is None or str(dict(row).get("hypothesis_id")) in hypothesis_ids)
    ]
    history = load_compiler_reports(root, limit=2500)
    normalization = dict(
        dict(load_project_evolution_policy().get("self_improvement") or {})
        .get("hypothesis_holdout", {}).get("signature_normalization") or {}
    )
    plugin_config = _admission_config(case_timeout_seconds, total_timeout_seconds)
    retries = _timeout_retries(timeout_retry_multipliers)
    handler = admission or _candidate_selection_admission
    trials = []
    promotion_count = 0
    for index, hypothesis in enumerate(hypotheses, start=1):
        _emit(progress, "compiled_hypothesis_started", index=index, hypothesis_id=hypothesis["hypothesis_id"])
        matches = _matching_reports(hypothesis, history, normalization)
        controls = _counterexample_paths(hypothesis, history)
        promotion_requested = promote and promotion_count < max(0, maximum_promotions)
        snapshot = capture_selection_state(root) if promotion_requested else None
        result = _trial_hypothesis(
            root, hypothesis, matches, controls, plugin_config, handler,
            promote=promotion_requested,
            maximum_holdouts=max(1, maximum_holdouts_per_hypothesis), progress=progress,
            timeout_retry_multipliers=retries,
            retry_quarantined=retry_quarantined,
        )
        if result.get("status") == "promoted" and (admission is None or repository_verifier):
            repository_gate = run_repository_gate(root, repository_verifier)
            if repository_gate.get("status") != "passed":
                rollback_selection_state(root, snapshot)
                result = reject_promoted_result(result, repository_gate)
            else:
                result["repository_regression_gate"] = repository_gate
        trials.append(result)
        promotion_count += int(result.get("status") == "promoted")
        _emit(
            progress, "compiled_hypothesis_completed", index=index,
            hypothesis_id=hypothesis["hypothesis_id"], status=result.get("status"),
        )
    trials.extend(run_specialized_trials(
        root=root, hypotheses=all_hypotheses, history=history,
        candidate_types=candidate_types, promote=promote,
        maximum_holdouts=max(1, maximum_holdouts_per_hypothesis),
        hypothesis_ids=hypothesis_ids,
        maximum_promotions=max(0, maximum_promotions - promotion_count), progress=progress,
    ))
    promotion_count += sum(row.get("status") == "promoted" for row in trials[len(hypotheses):])
    summary = _summary(trials, promotion_count)
    report = {
        "artifact_type": "CompiledHypothesisTrialReport",
        "status": "completed",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_compilation": compilation_path.as_posix(),
        "promotion_requested": promote,
        "summary": summary,
        "trials": trials,
    }
    if write:
        directory = root / "artifacts" / "hypothesis_compiler"
        directory.mkdir(parents=True, exist_ok=True)
        latest = directory / "compiled_hypothesis_trials.json"
        _archive_previous_report(latest, directory)
        stamp = _report_stamp(str(report["generated_at"]))
        path = directory / f"compiled_hypothesis_trials_{stamp}.json"
        encoded = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        path.write_text(encoded, encoding="utf-8")
        latest.write_text(encoded, encoding="utf-8")
        report.update({"report_path": path.as_posix(), "latest_report_path": latest.as_posix()})
    return report


def _trial_hypothesis(
    root: Path, hypothesis: dict[str, Any], matches: list[dict[str, Any]],
    controls: list[Path], plugin_config: dict[str, Any], admission: Admission, *,
    promote: bool, maximum_holdouts: int, progress=None,
    timeout_retry_multipliers: tuple[float, ...] = (),
    retry_quarantined: bool = False,
) -> dict[str, Any]:
    if not matches:
        return _trial_result(hypothesis, "blocked", reason="measured_holdout_missing")
    preflights = []
    selected = None
    for report in matches[:maximum_holdouts]:
        context = _admission_context(
            root, report, controls, plugin_config, promote=False, progress=progress,
        )
        outcome = admission(context)
        preflights.append({
            "project": report.get("project"), "status": outcome.get("status"),
            "reason": outcome.get("reason"), "policy_id": outcome.get("policy_id"),
        })
        if outcome.get("status") == "trial_passed":
            if not retry_quarantined and _quarantined_policy(root, str(outcome.get("policy_id") or "")):
                return _trial_result(
                    hypothesis, "quarantined", preflights=preflights,
                    reason="prior_repository_regression",
                )
            selected = report
            break
        if outcome.get("reason") == "selection_policy_already_active":
            return _trial_result(
                hypothesis, "already_covered", preflights=preflights,
                reason="selection_policy_already_active",
            )
    if selected is None:
        return _trial_result(
            hypothesis, "preflight_rejected", preflights=preflights,
            reason=str(preflights[-1].get("reason") if preflights else "preflight_missing"),
        )
    if not promote:
        return _trial_result(
            hypothesis, "trial_ready", holdout_project=selected.get("project"),
            counterexample_count=len(controls), preflights=preflights,
        )
    if not controls:
        return _trial_result(
            hypothesis, "blocked", holdout_project=selected.get("project"),
            preflights=preflights, reason="counterexample_paths_missing",
        )
    _emit(
        progress, "compiled_hypothesis_regression_started",
        hypothesis_id=hypothesis["hypothesis_id"], project=selected.get("project"),
        counterexample_count=len(controls),
    )
    outcome = admission(_admission_context(
        root, selected, controls, plugin_config, promote=True, progress=progress,
    ))
    admission_attempts = [_attempt_record(outcome, plugin_config)]
    for multiplier in timeout_retry_multipliers:
        if not _timeout_block(outcome):
            break
        retry_config = {
            **plugin_config,
            "regression_case_timeout_seconds": (
                float(plugin_config["regression_case_timeout_seconds"]) * multiplier
            ),
            "regression_total_timeout_seconds": (
                float(plugin_config["regression_total_timeout_seconds"]) * multiplier
            ),
        }
        _emit(
            progress, "compiled_hypothesis_timeout_retry_started",
            hypothesis_id=hypothesis["hypothesis_id"], multiplier=multiplier,
        )
        outcome = admission(_admission_context(
            root, selected, controls, retry_config, promote=True, progress=progress,
        ))
        admission_attempts.append(_attempt_record(outcome, retry_config))
    return _trial_result(
        hypothesis, str(outcome.get("status") or "blocked"),
        holdout_project=selected.get("project"), counterexample_count=len(controls),
        preflights=preflights, admission=outcome,
        admission_attempts=admission_attempts,
        reason=outcome.get("reason"),
    )


def _matching_reports(
    hypothesis: dict[str, Any], history: list[dict[str, Any]], normalization: dict[str, Any],
) -> list[dict[str, Any]]:
    evidence = {str(value) for value in hypothesis.get("evidence_refs") or []}
    grouped: dict[str, dict[str, Any]] = {}
    for report in history:
        compact = compact_report(report, normalization)
        project = str(compact.get("project") or "")
        if (
            project not in evidence
            or compact["portable_signature"] != hypothesis.get("portable_signature")
            or compact["semantic_context"] != list(hypothesis.get("semantic_context") or [])
            or not _measured_reselection(report)
            or not Path(str(report.get("project_dir") or "")).is_dir()
        ):
            continue
        prior = grouped.get(project)
        if prior is None or _score_delta(report) > _score_delta(prior):
            grouped[project] = report
    return sorted(grouped.values(), key=lambda row: (-_score_delta(row), str(row.get("project") or "")))


def _counterexample_paths(
    hypothesis: dict[str, Any], history: list[dict[str, Any]],
) -> list[Path]:
    wanted = {str(value) for value in hypothesis.get("counterexample_refs") or []}
    paths: dict[str, Path] = {}
    for report in history:
        project = str(report.get("project") or "")
        path = Path(str(report.get("project_dir") or ""))
        if project in wanted and path.is_dir():
            paths.setdefault(project, path)
    return [paths[key] for key in sorted(paths)]


def _admission_context(
    root: Path, report: dict[str, Any], controls: list[Path],
    plugin_config: dict[str, Any], *, promote: bool, progress=None,
) -> dict[str, Any]:
    baseline = dict(report.get("baseline") or {})
    trained = dict(report.get("trained_attempt") or {})
    source = str(baseline.get("selected_extraction_candidate") or "")
    challenger = str(trained.get("selected_extraction_candidate") or "")
    diagnosis = {
        **dict(report.get("diagnosis") or {}),
        "recommended_source": challenger,
        "measured_selection_effect": {
            "status": "confirmed_selection_effect",
            "source": source, "challenger": challenger,
            "score_delta": _score_delta(report), "role_regressions": [],
            "control": baseline, "treatment": trained,
        },
    }
    return {
        "root": root,
        "project_dir": Path(str(report["project_dir"])),
        "failure_packet": {
            "selected_candidate": source,
            "downstream_evidence": dict(baseline.get("downstream_evidence") or {}),
        },
        "diagnosis": diagnosis,
        "regression_projects": controls,
        "promote": promote,
        "requires_regression_cases": True,
        "plugin_config": plugin_config,
        "progress": progress,
    }


def _admission_config(case_timeout: float, total_timeout: float) -> dict[str, Any]:
    plugin = next(
        row for row in enabled_improvement_plugins()
        if row["id"] == "candidate_selection_admission"
    )
    return {
        **plugin,
        "regression_case_timeout_seconds": max(0.1, case_timeout),
        "regression_total_timeout_seconds": max(0.1, total_timeout),
    }


def _timeout_retries(values: tuple[float, ...] | None) -> tuple[float, ...]:
    if values is not None:
        return tuple(value for value in values if value > 1.0)
    policy = dict(load_hypothesis_compiler_config().get("trial_policy") or {})
    limit = max(0, int(policy.get("maximum_timeout_retries") or 0))
    return tuple(float(value) for value in policy.get("timeout_retry_multipliers") or [])[:limit]


def _timeout_block(outcome: dict[str, Any]) -> bool:
    return str(outcome.get("reason") or "") in {
        "regression_case_timeout", "regression_total_timeout",
    }


def _attempt_record(outcome: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": outcome.get("status"), "reason": outcome.get("reason"),
        "case_timeout_seconds": config.get("regression_case_timeout_seconds"),
        "total_timeout_seconds": config.get("regression_total_timeout_seconds"),
    }


def _quarantined_policy(root: Path, policy_id: str) -> bool:
    path = root / "knowledge" / "role_knowledge" / "promoted_candidate_selection_policies.json"
    if not policy_id or not path.exists():
        return False
    try:
        rows = list(json.loads(path.read_text(encoding="utf-8")).get("policies") or [])
    except (OSError, json.JSONDecodeError):
        return False
    return any(
        str(dict(row or {}).get("id") or "") == policy_id
        and dict(row or {}).get("activation_state") == "quarantined"
        for row in rows
    )


def _measured_reselection(report: dict[str, Any]) -> bool:
    baseline = dict(report.get("baseline") or {})
    trained = dict(report.get("trained_attempt") or {})
    return (
        _score_delta(report) > 0
        and baseline.get("selected_extraction_candidate")
        and trained.get("selected_extraction_candidate")
        and baseline["selected_extraction_candidate"] != trained["selected_extraction_candidate"]
        and not list(dict(report.get("outcome") or {}).get("role_regressions") or [])
    )


def _score_delta(report: dict[str, Any]) -> float:
    return float(dict(report.get("outcome") or {}).get("score_delta") or 0.0)


def _trial_result(hypothesis: dict[str, Any], status: str, **values: Any) -> dict[str, Any]:
    return {
        "hypothesis_id": hypothesis.get("hypothesis_id"),
        "candidate_type": hypothesis.get("candidate_type"),
        "status": status, **{key: value for key, value in values.items() if value is not None},
    }


def _summary(trials: list[dict[str, Any]], promotions: int) -> dict[str, Any]:
    statuses: dict[str, int] = {}
    for row in trials:
        status = str(row.get("status") or "unknown")
        statuses[status] = statuses.get(status, 0) + 1
    return {
        "hypothesis_count": len(trials), "promotion_count": promotions,
        "trial_ready_count": statuses.get("trial_ready", 0),
        "preflight_rejected_count": statuses.get("preflight_rejected", 0),
        "statuses": dict(sorted(statuses.items())),
    }


def _candidate_selection_admission(context: dict[str, Any]) -> dict[str, Any]:
    from .improvement_plugins.candidate_selection_admission import run

    return run(context)


def _archive_previous_report(latest: Path, directory: Path) -> None:
    if not latest.exists():
        return
    try:
        payload = json.loads(latest.read_text(encoding="utf-8"))
        stamp = _report_stamp(str(payload.get("generated_at") or "unknown"))
    except (OSError, json.JSONDecodeError):
        stamp = "unreadable"
    archive = directory / f"compiled_hypothesis_trials_{stamp}.json"
    if not archive.exists():
        archive.write_bytes(latest.read_bytes())


def _report_stamp(value: str) -> str:
    return "".join(character for character in value if character.isalnum()) or "unknown"


def _emit(sink, stage: str, **details: Any) -> None:
    if sink:
        sink({"stage": stage, **details})
