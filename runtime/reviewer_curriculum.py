"""Reviewer curriculum evaluator for teacher-reference projects."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .configured_role_pipeline import artifact_by_type, run_configured_role_prefix
from .project_benchmark import analyze_project
from .role_artifact_quality import evaluate_review_findings


REFERENCE_QUALITY = "teacher_reference_not_ground_truth"
IMPROVEMENT_PROTOCOL = "external_teacher_corrector_loop"
READY_THRESHOLD = 0.92


def run_reviewer_curriculum(
    *,
    root: Path,
    curriculum_dir: Path,
    write: bool = False,
) -> dict[str, Any]:
    cases = [run_curriculum_case(root=root, reference_path=path) for path in _reference_paths(curriculum_dir)]
    report = _report(cases, curriculum_dir=curriculum_dir)
    if write:
        out_dir = root / "artifacts" / "curricula"
        out_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        path = out_dir / f"reviewer_curriculum_{stamp}.json"
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        report["report_path"] = path.as_posix()
    return report


def run_curriculum_case(*, root: Path, reference_path: Path) -> dict[str, Any]:
    reference = json.loads(reference_path.read_text(encoding="utf-8"))
    _validate_teacher_reference(reference_path, reference)
    project_dir = _resolve_project_dir(root, reference_path, reference)
    project_report = analyze_project(project_dir)["project_map_report"]
    artifacts = run_configured_role_prefix(
        goal=f"Reviewer curriculum pass for {reference_path.parent.name}",
        project_report=project_report,
        until_artifact_type="ReviewFindings",
    )
    review = artifact_by_type(artifacts, "ReviewFindings")
    actual = _actual_review(review)
    score = _score_review(dict(reference.get("expected_review", {})), actual, review)
    backlog = _improvement_backlog(score)
    passed = score["score"] >= READY_THRESHOLD and not backlog
    return {
        "case": reference_path.parent.name,
        "project_dir": project_dir.as_posix(),
        "status": "ok" if passed else "needs_improvement",
        "score": score,
        "teacher_reference": {
            "reference_quality": reference.get("reference_quality"),
            "teacher_profile": reference.get("teacher_profile"),
            "improvement_protocol": IMPROVEMENT_PROTOCOL,
        },
        "actual": actual,
        "teacher_review": _teacher_review(reference.get("teacher_review", {}), backlog),
        "improvement_backlog": backlog,
    }


def _actual_review(review: dict[str, Any]) -> dict[str, Any]:
    target = dict(review.get("review_target", {}))
    coverage = dict(review.get("coverage_assessment", {}))
    checks = list(review.get("conformance_checks", []))
    return {
        "artifact_type": review.get("artifact_type"),
        "role": review.get("role"),
        "candidate": target.get("candidate"),
        "implementation_target": target.get("implementation_target"),
        "test_target": target.get("test_target"),
        "binding_status": target.get("binding_status"),
        "target_covered": coverage.get("target_covered"),
        "scope_preserved": coverage.get("scope_preserved"),
        "contract_matrix_rows": coverage.get("contract_matrix_rows"),
        "negative_test_count": coverage.get("negative_test_count"),
        "conformance_status": review.get("conformance_status"),
        "conformance_check_count": len(checks),
        "failed_conformance_checks": sorted(str(row.get("code")) for row in checks if isinstance(row, dict) and not row.get("passed")),
        "finding_codes": sorted(str(row.get("code")) for row in list(review.get("findings", [])) if isinstance(row, dict)),
        "risk_count": len(review.get("risk_assessment", []) if isinstance(review.get("risk_assessment"), list) else []),
        "contract_violation_count": len(review.get("contract_violations", []) if isinstance(review.get("contract_violations"), list) else []),
        "architecture_drift_count": len(review.get("architecture_drift", []) if isinstance(review.get("architecture_drift"), list) else []),
        "rework_task_count": len(review.get("rework_tasks", []) if isinstance(review.get("rework_tasks"), list) else []),
        "recommendation": review.get("recommendation"),
        "forbidden_actions_observed": _strings(review.get("forbidden_actions_observed", [])),
    }


def _score_review(expected: dict[str, Any], actual: dict[str, Any], review: dict[str, Any]) -> dict[str, Any]:
    quality = evaluate_review_findings(review)
    expected_recommendation = str(expected.get("recommendation") or "approve_with_risks")
    checks = {
        "artifact_is_review_findings": actual.get("artifact_type") == "ReviewFindings" and actual.get("role") == "reviewer",
        "candidate_matches": actual.get("candidate") in {
            expected.get("candidate"), *list(expected.get("acceptable_candidates") or [])
        },
        "implementation_and_test_targets_match": actual.get("implementation_target") == actual.get("candidate")
        and actual.get("test_target") == actual.get("candidate"),
        "binding_is_usable": actual.get("binding_status") in {"bound_to_extraction_contract", "bound_to_product_contract"},
        "target_covered": actual.get("target_covered") is True,
        "scope_preserved": actual.get("scope_preserved") is True,
        "contract_matrix_present": int(actual.get("contract_matrix_rows") or 0) >= int(expected.get("min_contract_matrix_rows", 1)),
        "negative_tests_present": int(actual.get("negative_test_count") or 0) >= int(expected.get("min_negative_test_count", 2)),
        "conformance_passed": actual.get("conformance_status") == "passed" and not actual.get("failed_conformance_checks"),
        "conformance_checks_present": int(actual.get("conformance_check_count") or 0) >= int(expected.get("min_conformance_check_count", 6)),
        "no_contract_violations": int(actual.get("contract_violation_count") or 0) == 0,
        "no_architecture_drift": int(actual.get("architecture_drift_count") or 0) == 0,
        "risk_assessment_present": int(actual.get("risk_count") or 0) >= int(expected.get("min_risk_count", 1)),
        "recommendation_matches": actual.get("recommendation") == expected_recommendation,
        "rework_count_matches": int(actual.get("rework_task_count") or 0) == int(expected.get("rework_task_count", 0)),
        "quality_gate_passed": quality["passed"] is True and not quality.get("blocking_warnings"),
        "no_forbidden_actions_observed": not actual.get("forbidden_actions_observed"),
    }
    warnings = [name for name, ok in checks.items() if not ok]
    return {
        "score": _ratio(sum(1 for ok in checks.values() if ok), len(checks)),
        "checks": checks,
        "warnings": warnings,
        "quality": quality,
    }


def _report(cases: list[dict[str, Any]], *, curriculum_dir: Path) -> dict[str, Any]:
    passed = sum(1 for case in cases if case["status"] == "ok")
    scores = [float(case["score"]["score"]) for case in cases]
    avg_score = _ratio(sum(scores), len(scores))
    worst_case_score = round(min(scores), 4) if scores else 0.0
    milestone = "Reviewer Curriculum External-3 v0.1" if "external" in curriculum_dir.name else "Reviewer Curriculum Local-3 v0.1"
    return {
        "status": "ok" if passed == len(cases) and worst_case_score >= READY_THRESHOLD else "needs_improvement",
        "milestone": milestone,
        "generated_at": _now(),
        "project_count": len(cases),
        "passed": passed,
        "summary": {
            "score": avg_score,
            "avg_score": avg_score,
            "worst_case_score": worst_case_score,
            "ready_threshold": READY_THRESHOLD,
            "ready_by_worst_case": worst_case_score >= READY_THRESHOLD,
            "backlog_items": sum(len(case["improvement_backlog"]) for case in cases),
        },
        "invariants": {
            "teacher_reference_is_ground_truth": False,
            "improvement_protocol": IMPROVEMENT_PROTOCOL,
            "automatic_code_changes_from_own_output": False,
            "source_code_changes": False,
            "registry_changes": False,
            "foundry_or_promote_not_in_scope": True,
            "executor_not_in_scope": True,
        },
        "cases": cases,
    }


def _improvement_backlog(score: dict[str, Any]) -> list[dict[str, str]]:
    return [{"type": "REVIEWER_GAP", "check": warning} for warning in score["warnings"]]


def _teacher_review(value: Any, backlog: list[dict[str, str]]) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return {
        "project_condition": value.get("project_condition", ""),
        "expected_review_behavior": _strings(value.get("expected_review_behavior", [])),
        "known_risks": _strings(value.get("known_risks", [])),
        "status": "watch" if backlog else "covered_by_current_run",
    }


def _validate_teacher_reference(reference_path: Path, reference: dict[str, Any]) -> None:
    if reference.get("reference_quality") != REFERENCE_QUALITY:
        raise ValueError(f"{reference_path} must declare reference_quality={REFERENCE_QUALITY!r}")
    if reference.get("teacher_profile") != "reviewer":
        raise ValueError(f"{reference_path} must declare teacher_profile='reviewer'")
    if not isinstance(reference.get("expected_review"), dict):
        raise ValueError(f"{reference_path} must contain expected_review object")


def _reference_paths(curriculum_dir: Path) -> list[Path]:
    paths = sorted(curriculum_dir.glob("*/teacher_reference.json"))
    if not paths:
        raise FileNotFoundError(f"no Reviewer teacher references found in {curriculum_dir}")
    return paths


def _resolve_project_dir(root: Path, reference_path: Path, reference: dict[str, Any]) -> Path:
    project = Path(str(reference.get("project_dir") or reference_path.parent / "source"))
    if not project.is_absolute():
        project = root / project
    if not project.is_dir():
        raise FileNotFoundError(f"curriculum project not found: {project}")
    return project.resolve()


def _strings(value: Any) -> list[str]:
    if isinstance(value, list):
        return sorted(str(item) for item in value if item is not None)
    if value is None:
        return []
    return [str(value)]


def _ratio(numerator: float, denominator: float) -> float:
    return 1.0 if denominator == 0 else round(numerator / denominator, 4)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
