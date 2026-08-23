"""Discover and validate a measured hypothesis on small independent holdouts."""
from __future__ import annotations
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .self_improvement_capability_request import capability_development_requests
from .self_improvement_signatures import (
    assess_signature_match, diagnosis_envelope, normalize_failure_class, normalize_portable_signature,
    portable_failure_signature, recovery_metrics, signatures_match as _signatures_match,
)
from .self_improvement_plugin_foundry import resolve_plugin_requests
from .self_improvement_recovery_contract import recovery_contract
from .self_improvement_emergent_hypothesis import emergent_hypothesis_redirect
from .self_improvement_search_cursor import (
    advance_query_cursors, build_round_search_plan, prior_query_page_ends,
)
from .self_improvement_target_alignment import probe_for_plan, remember_retrieval_target

HoldoutDiscoverer = Callable[[dict[str, Any]], list[Path]]
Trainer = Callable[..., dict[str, Any]]
ProjectProbe = Callable[..., dict[str, Any]]
ProgressSink = Callable[[dict[str, Any]], None]

def run_hypothesis_validation(
    *, root: Path, training: list[dict[str, Any]], discover: HoldoutDiscoverer,
    trainer: Trainer, target_score: float, regression_projects: list[Path],
    promote_config: bool | None, write: bool, policy: dict[str, Any],
    probe: ProjectProbe | None = None, progress: ProgressSink | None = None,
) -> dict[str, Any]:
    plan = build_validation_plan(training, policy)
    if not plan:
        return _finish(root, write, "not_applicable", reason="portable_training_hypothesis_missing")
    plan["query_page_cursors"] = prior_query_page_ends(root, plan)
    minimum = int(plan["minimum_projects"])
    projects: list[Path] = []
    matching: list[tuple[Path, dict[str, Any] | None]] = []
    fresh_matching: set[str] = set()
    probe_results: list[dict[str, Any]] = []
    rounds: list[dict[str, Any]] = []
    discovered_count = 0
    observed = []
    excluded = set(plan["excluded_projects"])
    prior_projects = _limit_prior_projects(_prior_matching_projects(root, plan), minimum)
    for index, project in enumerate(prior_projects, start=1):
        _emit(progress, "holdout_prior_probe_started", index=index, project=project.name)
        try:
            prepared = probe_for_plan(probe, root, project, target_score, plan)
            summary = _probe_summary(project, prepared, plan)
            observed.append((project, prepared, summary, False))
            projects.append(project); excluded.add(project.name)
            probe_results.append({**summary, "evidence_source": "prior_validation"})
            if summary["matches_hypothesis"]:
                matching.append((project, prepared))
            _emit(progress, "holdout_prior_probe_completed", index=index, **summary)
        except Exception as exc:
            probe_results.append({
                "project": project.name, "project_dir": project.as_posix(),
                "matches_hypothesis": False, "status": "probe_failed",
                "evidence_source": "prior_validation", "error": f"{type(exc).__name__}: {exc}",
            })
    for round_number in range(1, int(plan["maximum_discovery_rounds"]) + 1):
        if _enough_matches(matching, fresh_matching, plan):
            break
        round_plan = build_round_search_plan(plan, round_number, excluded)
        _emit(progress, "holdout_discovery_round_started", round=round_number, hypothesis_id=round_plan["hypothesis_id"])
        try:
            discovered = discover(round_plan)
        except Exception as exc:  # Provider failures are evidence, not trial crashes.
            _emit(progress, "holdout_discovery_round_failed", round=round_number, error=f"{type(exc).__name__}: {exc}")
            return _finish(
                root, write, "blocked", plan=plan, reason="external_discovery_failed",
                error=f"{type(exc).__name__}: {exc}", discovery_rounds=rounds,
                discovered_project_count=discovered_count, matching_project_count=len(matching),
                prior_evidence_project_count=len(prior_projects), probe_results=probe_results,
            )
        fresh = _independent_projects(discovered, excluded)
        discovered_count += len(fresh)
        projects.extend(fresh); excluded.update(path.name for path in fresh)
        round_matches = 0
        for index, project in enumerate(fresh, start=1):
            _emit(progress, "holdout_probe_started", round=round_number, index=index, project=project.name)
            try:
                prepared = probe_for_plan(probe, root, project, target_score, round_plan)
                summary = _probe_summary(project, prepared, plan)
                observed.append((project, prepared, summary, True))
                if summary["matches_hypothesis"]:
                    matching.append((project, prepared)); fresh_matching.add(project.name.lower())
                    round_matches += 1
                probe_results.append(summary)
                _emit(progress, "holdout_probe_completed", round=round_number, index=index, **summary)
            except Exception as exc:
                failure = {
                    "project": project.name, "project_dir": project.as_posix(),
                    "matches_hypothesis": False, "status": "probe_failed",
                    "error": f"{type(exc).__name__}: {exc}",
                }
                probe_results.append(failure)
                _emit(progress, "holdout_probe_failed", round=round_number, index=index, **failure)
        advance_query_cursors(plan, round_plan)
        rounds.append({
            "round": round_number, "hypothesis_id": round_plan["hypothesis_id"],
            "search_page_start": round_plan["search_page_start"],
            "queries": round_plan["queries"],
            "discovered_project_count": len(fresh), "matching_project_count": round_matches,
        })
        _emit(progress, "holdout_discovery_round_completed", **rounds[-1])
        if _enough_matches(matching, fresh_matching, plan):
            break
    redirect = emergent_hypothesis_redirect(observed, plan, target_score)
    if len(matching) < minimum and redirect:
        matching = list(redirect.pop("matching")); fresh_matching = set(redirect.pop("fresh_matching"))
        plan["original_portable_signature"] = plan["portable_signature"]
        plan.update({"portable_signature": redirect["portable_signature"], "failure_class": redirect["failure_class"]})
        plan["emergent_redirect"] = redirect
    if len(projects) < minimum:
        return _finish(
            root, write, "blocked", plan=plan, reason="insufficient_independent_holdouts",
            discovered_project_count=discovered_count, discovery_rounds=rounds,
            prior_evidence_project_count=len(prior_projects), probe_results=probe_results,
        )
    if len(matching) < minimum:
        return _finish(
            root, write, "blocked", plan=plan, reason="insufficient_matching_holdouts",
            discovered_project_count=discovered_count, matching_project_count=len(matching),
            prior_evidence_project_count=len(prior_projects), discovery_rounds=rounds,
            probe_results=probe_results,
        )
    if len(fresh_matching) < int(plan["minimum_new_projects"]):
        return _finish(
            root, write, "blocked", plan=plan, reason="insufficient_new_matching_holdouts",
            discovered_project_count=discovered_count, matching_project_count=len(matching),
            new_matching_project_count=len(fresh_matching),
            prior_evidence_project_count=len(prior_projects), discovery_rounds=rounds,
            probe_results=probe_results,
        )
    matching.sort(key=lambda row: row[0].name.lower() not in fresh_matching)
    fresh_training = [row for row in matching if row[0].name.lower() in fresh_matching]
    reports = []; matching_projects = [path for path, _prepared in matching]
    for index, (project_dir, prepared) in enumerate(fresh_training[:int(plan["maximum_projects"])], start=1):
        _emit(progress, "holdout_training_started", index=index, project=project_dir.name)
        kwargs = dict(
            root=root, project_dir=project_dir, target_score=target_score,
            regression_projects=list(dict.fromkeys([
                *[path for path in regression_projects if path != project_dir],
                *[path for path in matching_projects if path != project_dir],
            ])),
            promote_config=promote_config, write=write,
        )
        if prepared is not None:
            kwargs["prepared_probe"] = prepared
        report = trainer(**kwargs)
        reports.append(report)
        _emit(progress, "holdout_training_completed", index=index, project=project_dir.name, status=report.get("status"))
    promotions = sum(_promotion_count(report) for report in reports)
    verified = sum(_verified(report, target_score) for report in reports)
    requests = capability_development_requests(
        root, [*training, *reports],
        minimum_projects=int(policy.get("minimum_capability_request_projects") or 3),
        signature_normalization=dict(plan.get("signature_normalization") or {}),
    )
    foundry = resolve_plugin_requests(requests, [*training, *reports])
    decision = (
        "hypothesis_promoted" if promotions else
        "plugin_candidate_rejected" if foundry["status"] == "candidate_rejected" else
        "capability_development_required" if requests else "evidence_accumulated"
    )
    return _finish(
        root, write,
        "completed", plan=plan, training=reports, promotion_count=promotions,
        discovered_project_count=discovered_count, matching_project_count=len(matching),
        new_matching_project_count=len(fresh_matching),
        verified_project_count=verified, prior_evidence_project_count=len(prior_projects),
        discovery_rounds=rounds, probe_results=probe_results,
        capability_development_requests=requests, plugin_foundry=foundry, decision=decision,
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
    settings = dict(policy.get("hypothesis_holdout") or {})
    normalization = dict(settings.get("signature_normalization") or {})
    failure_class = normalize_failure_class(
        str(diagnosis.get("failure_class") or "unknown"), normalization
    )
    if failure_class == "unknown":
        return {}
    signature = portable_failure_signature(report, normalization)
    queries = _validation_queries(settings, failure_class, signature)
    if not queries:
        return {}
    plan_version = str(settings.get("plan_version") or "hypothesis_holdout.v1")
    digest = hashlib.sha256(signature.encode()).hexdigest()[:12]
    providers = [str(value) for value in settings.get("providers") or [] if value]
    if not providers:
        providers = [str(settings.get("provider") or "gitlab")]
    return {
        "artifact_type": "HypothesisValidationPlan",
        "hypothesis_id": f"hvp_{digest}",
        "plan_version": plan_version,
        "failure_class": failure_class,
        "portable_signature": signature,
        "diagnosis_envelope": diagnosis_envelope(report, normalization),
        "queries": queries,
        "minimum_projects": max(2, int(settings.get("minimum_projects") or 2)),
        "minimum_emergent_redirect_projects": max(4, int(settings.get("minimum_emergent_redirect_projects") or 4)),
        "minimum_new_projects": max(0, int(settings.get("minimum_new_projects") or 0)),
        "maximum_projects": max(2, int(settings.get("maximum_projects") or 3)),
        "candidate_pool_projects": max(2, int(settings.get("candidate_pool_projects") or 6)),
        "clone_workers": max(1, int(settings.get("clone_workers") or 1)),
        "maximum_discovery_rounds": max(1, int(settings.get("maximum_discovery_rounds") or 1)),
        "maximum_search_pages": max(1, int(settings.get("maximum_search_pages") or 2)),
        "queries_per_round": max(1, int(settings.get("queries_per_round") or len(queries))),
        "providers": providers,
        "provider_policy_overrides": dict(settings.get("provider_policy_overrides") or {}),
        "signature_normalization": normalization,
        "structural_prescreen": dict(settings.get("structural_prescreen") or {}),
        "recovery_contract": recovery_contract(report),
        "excluded_projects": sorted({str(row.get("project") or "") for row in training if row.get("project")}),
        "source_project_mutation_allowed": False,
    }


def _validation_queries(
    settings: dict[str, Any], failure_class: str, signature: str
) -> list[str]:
    profiles = dict(settings.get("query_profiles") or {})
    fallback = list(profiles.get(failure_class) or profiles.get("default") or [])
    terms = dict(settings.get("signature_query_terms") or {})
    parts = signature.split("|", 2)
    effects = [item for item in (parts[1].split(",") if len(parts) > 1 else []) if item]
    output_basis = parts[2] if len(parts) > 2 else "unknown"
    effect_terms = [
        str(term) for effect in effects
        for term in list(dict(terms.get("effects") or {}).get(effect) or [])
    ]
    output_terms = [
        str(term) for term in list(dict(terms.get("output_bases") or {}).get(output_basis) or [])
    ]
    planned = []
    composition = dict(settings.get("query_composition") or {})
    if composition.get("enabled"):
        composite_limit = max(0, int(composition.get("maximum_queries") or 4))
        plain_effects = [term for term in effect_terms if ":" not in term]
        for effect_term in plain_effects:
            for output_term in [term for term in output_terms if ":" not in term]:
                if len(planned) >= composite_limit:
                    break
                planned.append(f"{effect_term} {output_term}")
            if len(planned) >= composite_limit:
                break
    for index in range(max(len(effect_terms), len(output_terms))):
        if index < len(effect_terms):
            planned.append(effect_terms[index])
        if index < len(output_terms):
            planned.append(output_terms[index])
    maximum = max(1, int(terms.get("maximum_queries") or 4))
    signature_limit = max(0, maximum - min(1, len(fallback)))
    return list(dict.fromkeys([*planned[:signature_limit], *fallback]))[:maximum]


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


def _limit_prior_projects(projects: list[Path], minimum: int) -> list[Path]:
    return projects[:max(0, minimum)]


def _enough_matches(
    matching: list[tuple[Path, dict[str, Any] | None]], fresh: set[str], plan: dict[str, Any]
) -> bool:
    return (
        len(matching) >= int(plan["minimum_projects"])
        and len(fresh) >= int(plan["minimum_new_projects"])
    )


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


def _probe_summary(project: Path, probe: dict[str, Any] | None, plan: dict[str, Any]) -> dict[str, Any]:
    diagnosis = dict((probe or {}).get("diagnosis") or {})
    baseline = dict((probe or {}).get("baseline") or {})
    normalization = dict(plan.get("signature_normalization") or {})
    actual = normalize_failure_class(str(diagnosis.get("failure_class") or ""), normalization)
    signature = portable_failure_signature(
        {"baseline": baseline, "diagnosis": diagnosis}, normalization
    ) if probe else None
    actual = actual or str(signature or "").split("|", 1)[0]
    assessment = assess_signature_match(
        str(signature or ""), str(plan["portable_signature"]),
        dict(plan.get("signature_normalization") or {}),
    ) if probe else {"matched": True, "match_kind": "not_measured"}
    return {
        "project": project.name, "project_dir": project.as_posix(),
        "project_min_score": baseline.get("project_min_score"),
        "retrieval_alignment": dict((probe or {}).get("retrieval_alignment") or {}),
        "failure_class": actual or None, "portable_signature": signature,
        "matches_hypothesis": probe is None or bool(assessment["matched"]),
        "signature_assessment": assessment,
    }


def _probe_matches(probe: dict[str, Any], plan: dict[str, Any]) -> bool:
    diagnosis = dict(probe.get("diagnosis") or {})
    normalization = dict(plan.get("signature_normalization") or {})
    actual_signature = portable_failure_signature(
        {"baseline": dict(probe.get("baseline") or {}), "diagnosis": diagnosis}, normalization,
    )
    return _signatures_match(
        actual_signature,
        str(plan["portable_signature"]),
        dict(plan.get("signature_normalization") or {}),
    )


def _prior_matching_projects(root: Path, plan: dict[str, Any]) -> list[Path]:
    directory = root / "artifacts" / "self_improvement"
    boundary = (root / "artifacts" / "hypothesis_holdouts").resolve()
    projects: dict[str, Path] = {}
    for path in sorted(directory.glob("hypothesis_validation_*.json"), reverse=True):
        try:
            report = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        prior_plan = dict(report.get("plan") or {})
        normalization = dict(plan.get("signature_normalization") or {})
        if not _signatures_match(
                normalize_portable_signature(str(prior_plan.get("portable_signature") or ""), normalization),
                str(plan["portable_signature"]), normalization,
            ):
            continue
        for row in list(report.get("probe_results") or []):
            if not isinstance(row, dict):
                continue
            row_signature = normalize_portable_signature(
                str(row.get("portable_signature") or ""), normalization
            )
            if not _signatures_match(
                    row_signature, str(plan["portable_signature"]), normalization,
                ):
                continue
            project = Path(str(row.get("project_dir") or "")).resolve()
            if project.is_dir() and project.is_relative_to(boundary):
                projects.setdefault(project.name.lower(), project)
                remember_retrieval_target(plan, row, project)
    return list(projects.values())


def _emit(sink: ProgressSink | None, stage: str, **details: Any) -> None:
    if sink:
        sink({"stage": stage, **details})


def _finish(root: Path, write: bool, status: str, **values: Any) -> dict[str, Any]:
    probes = list(values.get("probe_results") or [])
    if probes:
        values["recovery_metrics"] = recovery_metrics(probes)
    result = _result(status, **values)
    if write:
        directory = root / "artifacts" / "self_improvement"
        directory.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        path = directory / f"hypothesis_validation_{stamp}.json"
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        result["report_path"] = path.as_posix()
    return result
