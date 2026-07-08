"""Benchmark role pipeline quality across project analyzer corpus."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .local_inference import LocalInferenceConfig
from .role_pipeline import run_role_pipeline


REQUIRED_ARTIFACTS = [
    "architecture_decision",
    "technical_spec",
    "implementation_plan",
    "test_plan",
    "review_findings",
]


def run_role_pipeline_benchmark(
    root: Path,
    *,
    benchmarks_dir: Path,
    write: bool = False,
    architect_advisory_config: LocalInferenceConfig | None = None,
) -> dict[str, Any]:
    projects_dir = benchmarks_dir / "projects"
    cases = []
    for project_dir in sorted(path for path in projects_dir.iterdir() if path.is_dir()):
        cases.append(
            run_role_pipeline_case(
                root,
                project_dir,
                architect_advisory_config=architect_advisory_config,
                allow_llm=architect_advisory_config is not None,
            )
        )
    report = _suite_report(cases)
    if write:
        out_dir = root / "artifacts" / "field_trials"
        out_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        path = out_dir / f"role_pipeline_field_trial_{stamp}.json"
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        report["report_path"] = path.as_posix()
    return report


def run_role_pipeline_case(
    root: Path,
    project_dir: Path,
    architect_advisory_config: LocalInferenceConfig | None = None,
    allow_llm: bool = False,
) -> dict[str, Any]:
    expected_candidate = _expected_best_extraction_candidate(project_dir)
    result = run_role_pipeline(
        root=root,
        project_dir=project_dir,
        goal=f"Assess and prepare first safe transformation for {project_dir.name}",
        write=False,
        architect_advisory_config=architect_advisory_config,
    )
    score = score_role_pipeline(result, allow_llm=allow_llm, expected_candidate=expected_candidate)
    advisory = dict(result.get("architect_advisory", {}))
    role_quality = dict(result.get("role_quality", {}))
    return {
        "project": project_dir.name,
        "status": "ok" if score["passed"] else "failed",
        "score": score,
        "architect_advisory": advisory,
        "advisory_quality": _advisory_quality(advisory),
        "role_quality": role_quality,
        "expected_best_extraction_candidate": expected_candidate,
        "next_action": result.get("next_action"),
        "recommendation": result.get("recommendation"),
    }


def score_role_pipeline(
    result: dict[str, Any],
    *,
    allow_llm: bool = False,
    expected_candidate: str | None = None,
) -> dict[str, Any]:
    artifacts = dict(result.get("artifacts", {}))
    safety = dict(result.get("safety", {}))
    role_quality = dict(result.get("role_quality", {}))
    checks = {
        "all_artifacts_present": all(key in artifacts for key in REQUIRED_ARTIFACTS),
        "review_has_recommendation": result.get("recommendation") in {"approve", "approve_with_risks", "request_rework"},
        "next_action_valid": result.get("next_action")
        in {"run_project_transform", "review_risks_then_run_project_transform", "rework_role_artifacts"},
        "implementer_targets_extraction_candidate": role_quality.get("implementation_targets_extraction_candidate") is True,
        "implementer_has_bound_input_contract": role_quality.get("implementation_has_input_contract") is True,
        "implementer_has_bound_output_contract": role_quality.get("implementation_has_output_contract") is True,
        "tester_targets_implementation_target": role_quality.get("test_targets_implementation_target") is True,
        "tester_has_contract_matrix": role_quality.get("test_has_contract_matrix") is True,
        "tester_has_negative_tests_for_target": role_quality.get("test_has_negative_tests_for_target") is True,
        "reviewer_targets_implementation_target": role_quality.get("review_targets_implementation_target") is True,
        "reviewer_confirms_target_coverage": role_quality.get("review_confirms_target_coverage") is True,
        "reviewer_has_no_contract_violations": role_quality.get("review_contract_violations") == 0,
        "no_source_changes": safety.get("source_code_changes") is False,
        "no_registry_changes": safety.get("registry_changes") is False,
        "no_foundry_by_default": safety.get("foundry_invoked") is False,
        "llm_policy_ok": allow_llm or safety.get("llm_invoked") is False,
    }
    if expected_candidate:
        checks["implementer_matches_expected_candidate"] = role_quality.get("implementation_target") == expected_candidate
    artifact_checks = [
        dict(artifacts.get("architecture_decision", {})).get("artifact_type") == "ArchitectureDecisionRecord",
        dict(artifacts.get("technical_spec", {})).get("artifact_type") == "TechnicalSpec",
        dict(artifacts.get("implementation_plan", {})).get("artifact_type") == "ImplementationPlan",
        dict(artifacts.get("test_plan", {})).get("artifact_type") == "TestPlan",
        dict(artifacts.get("review_findings", {})).get("artifact_type") == "ReviewFindings",
    ]
    implementation_checks = [
        checks["implementer_targets_extraction_candidate"],
        checks["implementer_has_bound_input_contract"],
        checks["implementer_has_bound_output_contract"],
    ]
    if expected_candidate:
        implementation_checks.append(checks["implementer_matches_expected_candidate"])
    qa_checks = [
        checks["tester_targets_implementation_target"],
        checks["tester_has_contract_matrix"],
        checks["tester_has_negative_tests_for_target"],
        checks["reviewer_targets_implementation_target"],
        checks["reviewer_confirms_target_coverage"],
        checks["reviewer_has_no_contract_violations"],
    ]
    safety_checks = [checks[key] for key in ("no_source_changes", "no_registry_changes", "no_foundry_by_default", "llm_policy_ok")]
    warnings = [name for name, ok in checks.items() if not ok]
    return {
        "passed": all(checks.values()) and all(artifact_checks),
        "artifact_score": _ratio(sum(1 for ok in artifact_checks if ok), len(artifact_checks)),
        "implementation_score": _ratio(sum(1 for ok in implementation_checks if ok), len(implementation_checks)),
        "qa_score": _ratio(sum(1 for ok in qa_checks if ok), len(qa_checks)),
        "safety_score": _ratio(sum(1 for ok in safety_checks if ok), len(safety_checks)),
        "checks": checks,
        "warnings": warnings,
    }


def _suite_report(cases: list[dict[str, Any]]) -> dict[str, Any]:
    passed = sum(1 for case in cases if case["score"]["passed"])
    artifact_score = _ratio(sum(case["score"]["artifact_score"] for case in cases), len(cases))
    implementation_score = _ratio(sum(case["score"]["implementation_score"] for case in cases), len(cases))
    qa_score = _ratio(sum(case["score"]["qa_score"] for case in cases), len(cases))
    safety_score = _ratio(sum(case["score"]["safety_score"] for case in cases), len(cases))
    advisories = [dict(case.get("architect_advisory", {})) for case in cases]
    qualities = [dict(case.get("advisory_quality", {})) for case in cases]
    delta_score = _ratio(sum(int(item.get("advisory_delta_score") or 0) for item in advisories), len(cases))
    return {
        "status": "ok" if passed == len(cases) else "failed",
        "milestone": "Role Pipeline Field Trial v0.1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "project_count": len(cases),
        "passed": passed,
        "summary": {
            "artifact_score": artifact_score,
            "implementation_score": implementation_score,
            "qa_score": qa_score,
            "safety_score": safety_score,
            "advisory_delta_score": delta_score,
            "advisory_accepted": sum(1 for item in advisories if item.get("accepted") is True),
            "advisory_quality": _merge_quality(qualities),
            "llm_invoked": sum(1 for item in advisories if item.get("llm_invoked") is True),
            "warnings": sum(len(case["score"]["warnings"]) for case in cases),
        },
        "cases": cases,
    }


def _ratio(numerator: float, denominator: float) -> float:
    return 1.0 if denominator == 0 else round(numerator / denominator, 4)


def _advisory_quality(advisory: dict[str, Any]) -> dict[str, Any]:
    tags = list(advisory.get("quality_tags", []))
    rejected = [
        str(item.get("reason"))
        for item in advisory.get("rejected_items", [])
        if isinstance(item, dict) and item.get("reason")
    ]
    return {
        "accepted_risk_count": len(advisory.get("accepted_risks", [])),
        "quality_tags": sorted(set(tags)),
        "quality_tag_counts": _counts(tags),
        "rejected_reason_counts": _counts(rejected),
    }


def _merge_quality(rows: list[dict[str, Any]]) -> dict[str, Any]:
    tag_counts: dict[str, int] = {}
    rejected_counts: dict[str, int] = {}
    accepted_risks = 0
    for row in rows:
        accepted_risks += int(row.get("accepted_risk_count") or 0)
        _add_counts(tag_counts, dict(row.get("quality_tag_counts", {})))
        _add_counts(rejected_counts, dict(row.get("rejected_reason_counts", {})))
    return {
        "accepted_risk_count": accepted_risks,
        "quality_tag_counts": dict(sorted(tag_counts.items())),
        "rejected_reason_counts": dict(sorted(rejected_counts.items())),
    }


def _counts(values: list[str]) -> dict[str, int]:
    result: dict[str, int] = {}
    for value in values:
        result[value] = result.get(value, 0) + 1
    return dict(sorted(result.items()))


def _add_counts(target: dict[str, int], source: dict[str, int]) -> None:
    for key, value in source.items():
        target[key] = target.get(key, 0) + int(value)


def _expected_best_extraction_candidate(project_dir: Path) -> str | None:
    path = project_dir / "expected_analysis.json"
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    expected = payload.get("expected_best_extraction_candidate")
    return str(expected) if expected else None
