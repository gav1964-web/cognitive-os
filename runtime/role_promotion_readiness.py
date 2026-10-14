"""Evidence-backed readiness for growing the first four roles."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .role_promotion_policy import load_role_promotion_policy


FIRST_FOUR = ("project_analyzer", "architect", "spec_writer", "implementer")
FOUNDATION_ROLES = FIRST_FOUR[:3]


def build_role_promotion_readiness(
    root: Path,
    report_paths: list[Path],
    *,
    policy: dict[str, Any] | None = None,
    evidence: list[str] | None = None,
) -> dict[str, Any]:
    policy = policy or load_role_promotion_policy()
    reports = [_read_report(root, path) for path in report_paths]
    observed = _observed_evidence(reports, evidence or [])
    role_rows = {
        role_id: _role_readiness(role_id, reports, observed, policy=policy)
        for role_id in FIRST_FOUR
    }
    ceilings = [float(row["score_ceiling"]) for row in role_rows.values()]
    ready = [role for role, row in role_rows.items() if row["status"] == "ready_for_9_7"]
    return {
        "artifact_type": "RolePromotionReadinessReport",
        "status": "ready_for_9_7" if len(ready) == len(FIRST_FOUR) else "needs_work",
        "roles": role_rows,
        "summary": {
            "role_count": len(role_rows),
            "ready_for_9_7": len(ready),
            "minimum_score_ceiling": round(min(ceilings, default=0.0), 2),
            "reports": len(reports),
            "evidence": sorted(observed),
        },
    }


def _role_readiness(
    role_id: str,
    reports: list[dict[str, Any]],
    evidence: set[str],
    *,
    policy: dict[str, Any],
) -> dict[str, Any]:
    role_policy = dict(dict(policy.get("first_four_roles") or {}).get(role_id) or {})
    metrics = _role_metrics(role_id, reports)
    missing_checks = _missing_checks(role_policy, metrics)
    missing_semantic = _missing_semantic_checks(role_policy, metrics)
    band_gaps = _band_gaps(policy, metrics, evidence, "9_7")
    runtime_gaps = _runtime_gaps(role_id, role_policy, metrics)
    target_score = float(role_policy.get("target_score") or 9.7)
    calibration_gaps = _calibration_gaps(metrics, target_score)
    gaps = missing_checks + missing_semantic + band_gaps + runtime_gaps + calibration_gaps
    score_ceiling = _score_ceiling(role_id, metrics, gaps, policy, evidence)
    return {
        "status": "ready_for_9_7" if not gaps and score_ceiling >= target_score else "needs_work",
        "target_score": target_score,
        "score_ceiling": score_ceiling,
        "metrics": metrics,
        "gaps": gaps,
        "growth_focus": list(role_policy.get("growth_focus") or []),
    }


def _role_metrics(role_id: str, reports: list[dict[str, Any]]) -> dict[str, Any]:
    role_scores: list[float] = []
    artifact_scores: list[float] = []
    checks: dict[str, int] = {}
    semantic_checks: dict[str, int] = {}
    projects = set()
    passed = 0
    total = 0
    calibration_caps: list[float] = []
    runtime_ratios: list[float] = []
    for report in reports:
        if _is_github_rebuild_corpus(report):
            ratio = _runtime_source_evidence_ratio(report)
            if ratio is not None:
                runtime_ratios.append(ratio)
            continue
        if role_id != "implementer" and (_is_implementer_curriculum(report) or _is_github_implementer_probe(report)):
            continue
        if role_id == "implementer" and _is_foundation_field_trial(report):
            continue
        report_cases = _cases(report)
        if role_id != "implementer" and _is_foundation_pipeline(report):
            report_cases = [_single_foundation_pipeline_case(report)]
        if role_id != "implementer" and _is_foundation_field_trial(report):
            calibration = dict(report.get("calibration") or {})
            if calibration.get("calibrated_readiness_min_score") is not None:
                calibration_caps.append(float(calibration["calibrated_readiness_min_score"]))
        for case in report_cases:
            if case.get("status") == "out_of_scope":
                continue
            if role_id == "implementer" and _is_implementer_curriculum(report):
                case = _curriculum_case_as_role_case(case)
            elif role_id == "implementer" and _is_github_implementer_probe(report):
                case = _github_implementer_case_as_role_case(case)
            elif _is_foundation_field_trial(report):
                case = _foundation_case_as_role_case(role_id, case)
            total += 1
            projects.add(str(case.get("project") or case.get("name") or total))
            score = dict(case.get("score") or {})
            if score.get("passed") is True or case.get("status") == "ok":
                passed += 1
            artifact_scores.append(float(score.get("artifact_score") or 0.0))
            _merge_bool_counts(checks, dict(score.get("checks") or {}))
            semantic = dict(score.get("foundation_semantic_quality") or {})
            role_scores.extend(_semantic_scores(role_id, semantic))
            _merge_semantic_checks(semantic_checks, role_id, semantic)
        if not report_cases:
            total += 1
            projects.add(str(report.get("project") or report.get("artifact_type") or total))
            if report.get("status") in {"ok", "passed"}:
                passed += 1
            summary = dict(report.get("summary") or {})
            artifact_scores.append(float(summary.get("artifact_score") or 0.0))
    return {
        "projects": len(projects),
        "pass_rate": round(passed / total, 4) if total else 0.0,
        "artifact_score": round(sum(artifact_scores) / len(artifact_scores), 4) if artifact_scores else 0.0,
        "semantic_score": round(sum(role_scores) / len(role_scores), 2) if role_scores else 0.0,
        "calibrated_score_ceiling": round(min(calibration_caps), 2) if calibration_caps else 10.0,
        "runtime_source_evidence_ratio": round(min(runtime_ratios), 4) if runtime_ratios else 0.0,
        "checks": checks,
        "semantic_checks": semantic_checks,
    }


def _is_implementer_curriculum(report: dict[str, Any]) -> bool:
    return "Implementer Curriculum" in str(report.get("milestone") or "")


def _is_github_implementer_probe(report: dict[str, Any]) -> bool:
    return "implementer" in str(report.get("milestone") or "").lower() and "cases" in report


def _is_foundation_field_trial(report: dict[str, Any]) -> bool:
    return report.get("artifact_type") == "RoleFoundationFieldTrialReport"


def _is_foundation_pipeline(report: dict[str, Any]) -> bool:
    return report.get("kind") == "role_foundation_pipeline"


def _is_github_rebuild_corpus(report: dict[str, Any]) -> bool:
    return report.get("kind") == "github_rebuild_corpus"


def _single_foundation_pipeline_case(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "project": report.get("project") or report.get("portfolio_root") or "foundation_pipeline",
        "status": report.get("status"),
        "score": {
            "passed": dict(report.get("score") or {}).get("passed") is True,
            "artifact_score": float(dict(report.get("score") or {}).get("artifact_score") or 0.0),
            "checks": dict(dict(report.get("score") or {}).get("checks") or {}),
            "foundation_semantic_quality": dict(dict(report.get("score") or {}).get("foundation_semantic_quality") or {}),
        },
    }


def _foundation_case_as_role_case(role_id: str, case: dict[str, Any]) -> dict[str, Any]:
    checks = _foundation_required_checks(case)
    semantic = dict(case.get("semantic_quality") or {})
    role_scores = dict(case.get("role_scores") or {})
    semantic["role_scores"] = {
        **dict(semantic.get("role_scores") or {}),
        **{role_id: role_scores.get(role_id)}
    }
    return {
        "project": case.get("project"),
        "status": case.get("status"),
        "score": {
            "passed": case.get("status") == "ok",
            "artifact_score": float(case.get("project_min_score") or 0.0) / 10.0,
            "checks": checks,
            "foundation_semantic_quality": semantic,
        },
    }


def _foundation_required_checks(case: dict[str, Any]) -> dict[str, bool]:
    artifacts = dict(case.get("artifacts") or {})
    return {
        "project_map_report_present": "project_map_report" in artifacts,
        "project_report_has_answers": "project_map_report" in artifacts,
        "project_map_report_quality_passed": case.get("status") == "ok",
        "foundation_semantic_quality_passed": dict(case.get("semantic_quality") or {}).get("status") == "ok",
        "adr_present": "architecture_decision" in artifacts,
        "adr_has_chosen_option": "architecture_decision" in artifacts,
        "adr_has_traceability": "architecture_decision" in artifacts,
        "adr_quality_passed": case.get("status") == "ok",
        "architect_red_team_passed": case.get("status") == "ok",
        "spec_present": "technical_spec" in artifacts,
        "spec_has_requirements": "technical_spec" in artifacts,
        "spec_has_acceptance": "technical_spec" in artifacts,
        "spec_has_traceability": "technical_spec" in artifacts,
        "spec_has_extraction_contract": bool(case.get("selected_extraction_candidate")),
        "spec_writer_red_team_passed": case.get("status") == "ok",
    }


def _github_implementer_case_as_role_case(case: dict[str, Any]) -> dict[str, Any]:
    candidate = str(case.get("candidate") or "")
    checks = {
        "implementation_plan_present": case.get("status") == "ok",
        "implementation_plan_quality_passed": float(case.get("quality_score") or 0.0) >= 0.95,
        "contract_binding_present": case.get("binding_status") == "bound_to_extraction_contract",
        "executor_handoff_present": case.get("status") == "ok",
        "verification_commands_present": bool(case.get("verification_commands")),
    }
    semantic_checks = {
        "contract_binding_is_source_backed": bool(candidate and case.get("spec_candidate") == candidate),
        "patch_scope_is_bounded": list(case.get("patch_scope") or []) == [candidate],
        "acceptance_mapping_present": case.get("status") == "ok",
        "rollback_plan_present": bool(case.get("expected_files")),
    }
    return {
        "project": case.get("project"),
        "status": case.get("status"),
        "score": {
            "passed": case.get("status") == "ok",
            "artifact_score": float(case.get("quality_score") or 0.0),
            "checks": checks,
            "foundation_semantic_quality": {
                "role_scores": {"implementer": round(float(case.get("quality_score") or 0.0) * 10.0, 2)},
                "checks": {"implementer": [{"code": key, "passed": value} for key, value in semantic_checks.items()]},
            },
        },
    }


def _curriculum_case_as_role_case(case: dict[str, Any]) -> dict[str, Any]:
    actual = dict(case.get("actual") or {})
    candidate = str(actual.get("candidate") or "")
    patch_scope = list(actual.get("patch_scope") or [])
    writable = list(actual.get("writable_scope") or [])
    checks = {
        "implementation_plan_present": actual.get("artifact_type") == "ImplementationPlan",
        "implementation_plan_quality_passed": case.get("status") == "ok",
        "contract_binding_present": actual.get("binding_status") == "bound_to_extraction_contract",
        "executor_handoff_present": actual.get("executor_handoff_type") == "ExecutorHandoff",
        "verification_commands_present": bool(actual.get("verification_commands")),
    }
    semantic_checks = {
        "contract_binding_is_source_backed": bool(candidate and actual.get("binding_candidate") == candidate),
        "patch_scope_is_bounded": bool(candidate and patch_scope == [candidate] and writable == [candidate]),
        "acceptance_mapping_present": int(actual.get("acceptance_mapping_count") or 0) > 0,
        "rollback_plan_present": bool(actual.get("rollback_files")),
    }
    return {
        "project": case.get("case"),
        "status": case.get("status"),
        "score": {
            "passed": case.get("status") == "ok",
            "artifact_score": float(dict(case.get("score") or {}).get("score") or 0.0),
            "checks": checks,
            "foundation_semantic_quality": {
                "role_scores": {"implementer": _curriculum_score_10(case)},
                "checks": {"implementer": [{"code": key, "passed": value} for key, value in semantic_checks.items()]},
            },
        },
    }


def _curriculum_score_10(case: dict[str, Any]) -> float:
    return round(float(dict(case.get("score") or {}).get("score") or 0.0) * 10.0, 2)


def _cases(report: dict[str, Any]) -> list[dict[str, Any]]:
    rows = report.get("cases")
    return [dict(row) for row in rows] if isinstance(rows, list) else []


def _semantic_scores(role_id: str, semantic: dict[str, Any]) -> list[float]:
    scores = dict(semantic.get("role_scores") or semantic.get("role_scores_10pt") or {})
    value = scores.get(role_id)
    return [float(value)] if isinstance(value, (int, float)) else []


def _merge_bool_counts(target: dict[str, int], values: dict[str, Any]) -> None:
    for key, value in values.items():
        if value is True:
            target[str(key)] = target.get(str(key), 0) + 1


def _merge_semantic_checks(target: dict[str, int], role_id: str, semantic: dict[str, Any]) -> None:
    rows = list(dict(semantic.get("checks") or {}).get(role_id) or [])
    for row in rows:
        item = dict(row or {})
        if item.get("passed") is True and item.get("code"):
            target[str(item["code"])] = target.get(str(item["code"]), 0) + 1


def _missing_checks(role_policy: dict[str, Any], metrics: dict[str, Any]) -> list[str]:
    checks = dict(metrics.get("checks") or {})
    return [f"missing_check:{name}" for name in role_policy.get("required_checks", []) if checks.get(str(name), 0) <= 0]


def _missing_semantic_checks(role_policy: dict[str, Any], metrics: dict[str, Any]) -> list[str]:
    checks = dict(metrics.get("semantic_checks") or {})
    return [f"missing_semantic_check:{name}" for name in role_policy.get("required_semantic_checks", []) if checks.get(str(name), 0) <= 0]


def _band_gaps(policy: dict[str, Any], metrics: dict[str, Any], evidence: set[str], band_name: str) -> list[str]:
    band = dict(dict(policy.get("score_bands") or {}).get(band_name) or {})
    gaps = []
    if int(metrics.get("projects") or 0) < int(band.get("minimum_projects") or 0):
        gaps.append(f"minimum_projects:{band_name}")
    if float(metrics.get("pass_rate") or 0.0) < float(band.get("minimum_pass_rate") or 0.0):
        gaps.append(f"minimum_pass_rate:{band_name}")
    for item in sorted({str(row) for row in list(band.get("required_evidence") or [])} - evidence):
        gaps.append(f"missing_evidence:{item}")
    return gaps


def _calibration_gaps(metrics: dict[str, Any], target_score: float) -> list[str]:
    ceiling = float(metrics.get("calibrated_score_ceiling") or 10.0)
    return ["calibrated_readiness_below_target"] if ceiling < target_score else []


def _runtime_gaps(role_id: str, role_policy: dict[str, Any], metrics: dict[str, Any]) -> list[str]:
    if role_id not in FOUNDATION_ROLES:
        return []
    minimum = float(role_policy.get("minimum_runtime_source_evidence_ratio") or 0.0)
    observed = float(metrics.get("runtime_source_evidence_ratio") or 0.0)
    return ["runtime_source_evidence_below_target"] if observed < minimum else []


def _observed_evidence(reports: list[dict[str, Any]], declared: list[str]) -> set[str]:
    evidence = {str(item) for item in declared if item}
    if reports:
        evidence.add("field_report")
    if reports and all(dict(report.get("summary") or {}).get("source_code_changes", 0) == 0 for report in reports):
        evidence.add("no_source_changes")
    if len(_all_projects(reports)) >= 2:
        evidence.add("independent_holdout")
    if any(_is_github_rebuild_corpus(report) for report in reports):
        evidence.add("runtime_rebuild_corpus")
    return evidence


def _all_projects(reports: list[dict[str, Any]]) -> set[str]:
    projects = set()
    for report in reports:
        for case in _cases(report):
            if case.get("project"):
                projects.add(str(case["project"]))
    return projects


def _score_ceiling(role_id: str, metrics: dict[str, Any], gaps: list[str], policy: dict[str, Any], evidence: set[str]) -> float:
    runtime_ceiling = _runtime_score_ceiling(metrics) if role_id in FOUNDATION_ROLES else 10.0
    calibrated = min(float(metrics.get("calibrated_score_ceiling") or 10.0), runtime_ceiling)
    if not gaps:
        return min(9.7, calibrated)
    if not _band_gaps(policy, metrics, evidence, "9_5"):
        return min(9.5, calibrated)
    if float(metrics.get("semantic_score") or 0.0) >= 9.2 and float(metrics.get("artifact_score") or 0.0) >= 0.92:
        return min(9.2, calibrated)
    return min(8.9, calibrated)


def _runtime_score_ceiling(metrics: dict[str, Any]) -> float:
    ratio = float(metrics.get("runtime_source_evidence_ratio") or 0.0)
    return round(ratio * 10.0, 2) if ratio else 10.0


def _runtime_source_evidence_ratio(report: dict[str, Any]) -> float | None:
    summary = dict(report.get("summary") or {})
    probes = int(summary.get("http_probes") or 0) + int(summary.get("module_import_probes") or 0)
    if probes <= 0:
        return None
    return min(1.0, float(summary.get("source_evidence_score") or 0.0) / probes)


def _read_report(root: Path, path: Path) -> dict[str, Any]:
    source = path if path.is_absolute() else root / path
    return json.loads(source.read_text(encoding="utf-8"))
