"""Tester curriculum evaluator for teacher-reference projects."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .configured_role_pipeline import artifact_by_type, producer_for_artifact_type, run_configured_role_prefix
from .project_benchmark import analyze_project
from .role_artifact_quality import evaluate_test_plan


REFERENCE_QUALITY = "teacher_reference_not_ground_truth"
IMPROVEMENT_PROTOCOL = "external_teacher_corrector_loop"
READY_THRESHOLD = 0.92


def run_tester_curriculum(
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
        path = out_dir / f"tester_curriculum_{stamp}.json"
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        report["report_path"] = path.as_posix()
    return report


def run_curriculum_case(*, root: Path, reference_path: Path) -> dict[str, Any]:
    reference = json.loads(reference_path.read_text(encoding="utf-8"))
    _validate_teacher_reference(reference_path, reference)
    project_dir = _resolve_project_dir(root, reference_path, reference)
    project_report = analyze_project(project_dir)["project_map_report"]
    artifacts = run_configured_role_prefix(
        goal=f"Tester curriculum pass for {reference_path.parent.name}",
        project_report=project_report,
        until_artifact_type="TestPlan",
    )
    plan = artifact_by_type(artifacts, "TestPlan")
    actual = _actual_plan(plan)
    score = _score_plan(dict(reference.get("expected_test_plan", {})), actual, plan)
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


def _actual_plan(plan: dict[str, Any]) -> dict[str, Any]:
    target = dict(plan.get("test_target", {}))
    strategy = dict(plan.get("test_strategy", {}))
    dependency = dict(plan.get("dependency_policy", {}))
    executable = dict(plan.get("executable_acceptance", {}))
    next_artifact = dict(plan.get("next_artifact", {}))
    return {
        "artifact_type": plan.get("artifact_type"),
        "role": plan.get("role"),
        "candidate": target.get("candidate"),
        "binding_status": target.get("binding_status"),
        "has_input_contract": isinstance(target.get("input_contract"), dict),
        "has_output_contract": bool(target.get("output_contract")),
        "strategy_target": strategy.get("target"),
        "writable_scope": _strings(strategy.get("writable_scope", [])),
        "read_only_context": _strings(strategy.get("read_only_context", [])),
        "evidence_scope": _strings(strategy.get("evidence_scope", [])),
        "contract_matrix_count": len(plan.get("contract_test_matrix", []) if isinstance(plan.get("contract_test_matrix"), list) else []),
        "acceptance_test_count": len(plan.get("acceptance_tests", []) if isinstance(plan.get("acceptance_tests"), list) else []),
        "negative_test_count": len(plan.get("negative_tests", []) if isinstance(plan.get("negative_tests"), list) else []),
        "smoke_count": len(plan.get("smoke_checklist", []) if isinstance(plan.get("smoke_checklist"), list) else []),
        "regression_risk_count": len(plan.get("regression_risks", []) if isinstance(plan.get("regression_risks"), list) else []),
        "executable_acceptance_status": executable.get("status"),
        "executable_obligation_count": len(executable.get("obligations", []) if isinstance(executable.get("obligations"), list) else []),
        "dependency_external_calls": dependency.get("external_calls"),
        "dependency_default_mode": dependency.get("default_mode"),
        "forbidden_actions_observed": _strings(plan.get("forbidden_actions_observed", [])),
        "next_role": next_artifact.get("recommended_role"),
    }


def _score_plan(expected: dict[str, Any], actual: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
    quality = evaluate_test_plan(plan)
    review_producer = producer_for_artifact_type("ReviewFindings")
    checks = {
        "artifact_is_test_plan": actual.get("artifact_type") == "TestPlan" and actual.get("role") == "tester",
        "candidate_matches": actual.get("candidate") == expected.get("candidate"),
        "strategy_targets_candidate": actual.get("strategy_target") == actual.get("candidate"),
        "binding_is_usable": actual.get("binding_status") in {"bound_to_extraction_contract", "bound_to_product_contract"},
        "has_contracts": actual.get("has_input_contract") is True and actual.get("has_output_contract") is True,
        "writable_scope_targets_expected": actual.get("writable_scope") == _strings(expected.get("writable_scope", [expected.get("candidate")])),
        "read_only_context_kept_separate": _read_only_context_kept_separate(actual),
        "contract_matrix_present": int(actual.get("contract_matrix_count") or 0) >= int(expected.get("min_contract_matrix_count", 1)),
        "acceptance_tests_present": int(actual.get("acceptance_test_count") or 0) >= int(expected.get("min_acceptance_test_count", 1)),
        "negative_tests_present": int(actual.get("negative_test_count") or 0) >= int(expected.get("min_negative_test_count", 2)),
        "smoke_commands_present": int(actual.get("smoke_count") or 0) >= int(expected.get("min_smoke_count", 1)),
        "regression_risks_present": int(actual.get("regression_risk_count") or 0) >= int(expected.get("min_regression_risk_count", 1)),
        "executable_acceptance_ready": actual.get("executable_acceptance_status") == "ready"
        and int(actual.get("executable_obligation_count") or 0) >= int(expected.get("min_executable_obligation_count", 2)),
        "dependency_policy_matches": _dependency_policy_matches(expected, actual),
        "quality_gate_passed": quality["passed"] is True and not quality.get("blocking_warnings"),
        "no_forbidden_actions_observed": not actual.get("forbidden_actions_observed"),
        "next_role_targets_reviewer": actual.get("next_role") == review_producer,
    }
    warnings = [name for name, ok in checks.items() if not ok]
    return {
        "score": _ratio(sum(1 for ok in checks.values() if ok), len(checks)),
        "checks": checks,
        "warnings": warnings,
        "quality": quality,
    }


def _read_only_context_kept_separate(actual: dict[str, Any]) -> bool:
    writable = set(_strings(actual.get("writable_scope", [])))
    read_only = set(_strings(actual.get("read_only_context", [])))
    return bool(writable) and not writable.intersection(read_only)


def _dependency_policy_matches(expected: dict[str, Any], actual: dict[str, Any]) -> bool:
    expected_mode = str(expected.get("dependency_external_calls") or "").strip()
    if not expected_mode:
        return True
    return actual.get("dependency_external_calls") == expected_mode


def _report(cases: list[dict[str, Any]], *, curriculum_dir: Path) -> dict[str, Any]:
    passed = sum(1 for case in cases if case["status"] == "ok")
    scores = [float(case["score"]["score"]) for case in cases]
    avg_score = _ratio(sum(scores), len(scores))
    worst_case_score = round(min(scores), 4) if scores else 0.0
    milestone = "Tester Curriculum External-3 v0.1" if "external" in curriculum_dir.name else "Tester Curriculum Local-3 v0.1"
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
            "reviewer_not_in_scope": True,
        },
        "cases": cases,
    }


def _improvement_backlog(score: dict[str, Any]) -> list[dict[str, str]]:
    return [{"type": "TESTER_GAP", "check": warning} for warning in score["warnings"]]


def _teacher_review(value: Any, backlog: list[dict[str, str]]) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return {
        "project_condition": value.get("project_condition", ""),
        "expected_test_behavior": _strings(value.get("expected_test_behavior", [])),
        "known_risks": _strings(value.get("known_risks", [])),
        "status": "watch" if backlog else "covered_by_current_run",
    }


def _validate_teacher_reference(reference_path: Path, reference: dict[str, Any]) -> None:
    if reference.get("reference_quality") != REFERENCE_QUALITY:
        raise ValueError(f"{reference_path} must declare reference_quality={REFERENCE_QUALITY!r}")
    if reference.get("teacher_profile") != "tester":
        raise ValueError(f"{reference_path} must declare teacher_profile='tester'")
    if not isinstance(reference.get("expected_test_plan"), dict):
        raise ValueError(f"{reference_path} must contain expected_test_plan object")


def _reference_paths(curriculum_dir: Path) -> list[Path]:
    paths = sorted(curriculum_dir.glob("*/teacher_reference.json"))
    if not paths:
        raise FileNotFoundError(f"no Tester teacher references found in {curriculum_dir}")
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
