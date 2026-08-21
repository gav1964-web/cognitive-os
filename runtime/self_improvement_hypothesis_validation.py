"""Discover and validate a measured hypothesis on small independent holdouts."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Callable


HoldoutDiscoverer = Callable[[dict[str, Any]], list[Path]]
Trainer = Callable[..., dict[str, Any]]


def run_hypothesis_validation(
    *, root: Path, training: list[dict[str, Any]], discover: HoldoutDiscoverer,
    trainer: Trainer, target_score: float, regression_projects: list[Path],
    promote_config: bool | None, write: bool, policy: dict[str, Any],
) -> dict[str, Any]:
    plan = build_validation_plan(training, policy)
    if not plan:
        return _result("not_applicable", reason="portable_training_hypothesis_missing")
    try:
        discovered = discover(plan)
    except Exception as exc:  # Provider failures are evidence, not trial crashes.
        return _result("blocked", plan=plan, reason="external_discovery_failed", error=f"{type(exc).__name__}: {exc}")
    projects = _independent_projects(discovered, set(plan["excluded_projects"]))
    minimum = int(plan["minimum_projects"])
    if len(projects) < minimum:
        return _result(
            "blocked", plan=plan, reason="insufficient_independent_holdouts",
            discovered_project_count=len(projects),
        )
    reports = []
    for project_dir in projects[:int(plan["maximum_projects"])]:
        reports.append(trainer(
            root=root, project_dir=project_dir, target_score=target_score,
            regression_projects=[path for path in regression_projects if path != project_dir],
            promote_config=promote_config, write=write,
        ))
    promotions = sum(_promotion_count(report) for report in reports)
    verified = sum(_verified(report, target_score) for report in reports)
    return _result(
        "completed", plan=plan, training=reports, promotion_count=promotions,
        discovered_project_count=len(projects), verified_project_count=verified,
        decision="hypothesis_promoted" if promotions else "evidence_accumulated",
    )


def build_validation_plan(
    training: list[dict[str, Any]], policy: dict[str, Any]
) -> dict[str, Any]:
    candidates = [
        report for report in training
        if report.get("knowledge_candidate_path") and not _promotion_count(report)
    ]
    if not candidates:
        return {}
    report = candidates[-1]
    diagnosis = dict(report.get("diagnosis") or {})
    failure_class = str(diagnosis.get("failure_class") or "unknown")
    if failure_class == "unknown":
        return {}
    settings = dict(policy.get("hypothesis_holdout") or {})
    profiles = dict(settings.get("query_profiles") or {})
    queries = list(profiles.get(failure_class) or profiles.get("default") or [])
    if not queries:
        return {}
    signature = _portable_signature(report)
    digest = hashlib.sha256(f"{failure_class}|{signature}".encode()).hexdigest()[:12]
    return {
        "artifact_type": "HypothesisValidationPlan",
        "hypothesis_id": f"hvp_{digest}",
        "failure_class": failure_class,
        "portable_signature": signature,
        "queries": queries,
        "minimum_projects": max(2, int(settings.get("minimum_projects") or 2)),
        "maximum_projects": max(2, int(settings.get("maximum_projects") or 3)),
        "maximum_search_pages": max(1, int(settings.get("maximum_search_pages") or 2)),
        "provider": str(settings.get("provider") or "gitlab"),
        "excluded_projects": sorted({str(row.get("project") or "") for row in training if row.get("project")}),
        "source_project_mutation_allowed": False,
    }


def _portable_signature(report: dict[str, Any]) -> str:
    baseline = dict(report.get("baseline") or {})
    evidence = dict(baseline.get("downstream_evidence") or {})
    quality = dict(baseline.get("selected_candidate_quality") or {})
    structural = dict(quality.get("structural_evidence") or {})
    effects = ",".join(sorted(str(value) for value in structural.get("observed_side_effects") or []))
    return "|".join([
        str(evidence.get("reason") or evidence.get("acceptance_signal") or "unclassified"),
        effects or "pure", str(structural.get("output_inference_basis") or "unknown"),
    ])


def _independent_projects(projects: list[Path], excluded: set[str]) -> list[Path]:
    result = []
    seen = set()
    for value in projects:
        path = Path(value).resolve()
        key = path.name.lower()
        if key in seen or path.name in excluded or not path.is_dir():
            continue
        seen.add(key); result.append(path)
    return result


def _promotion_count(report: dict[str, Any]) -> int:
    before = int(dict(report.get("improvement_plugin_cycle") or {}).get("promotion_count") or 0)
    after = int(dict(report.get("post_training_admission") or {}).get("promotion_count") or 0)
    return before + after


def _verified(report: dict[str, Any], target: float) -> bool:
    trained = dict(report.get("trained_attempt") or report.get("baseline") or {})
    score = float(trained.get("project_min_score") or 0.0)
    return report.get("status") == "already_at_target" or score >= target


def _result(status: str, **values: Any) -> dict[str, Any]:
    return {"artifact_type": "HypothesisValidationTrial", "status": status, **values}
