"""Adversarial artifact-mutation trial for Reviewer."""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .configured_role_pipeline import artifact_by_type, run_configured_role_prefix
from .project_benchmark import analyze_project
from .review_findings_builder import build_review_findings


Mutation = Callable[[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]], None]


def run_reviewer_adversarial_trial(*, root: Path, write: bool = False) -> dict[str, Any]:
    project_dir = root / "benchmarks" / "project_analyzer" / "projects" / "simple_cli_tool"
    project_report = analyze_project(project_dir)["project_map_report"]
    artifacts = run_configured_role_prefix(
        goal="Reviewer adversarial artifact mutation trial",
        project_report=project_report,
        until_artifact_type="TestPlan",
    )
    baseline = (
        artifact_by_type(artifacts, "TechnicalSpec"),
        artifact_by_type(artifacts, "ImplementationPlan"),
        artifact_by_type(artifacts, "TestPlan"),
        {"artifact_type": "TestResult", "status": "ok", "commands": [{"status": "passed", "exit_code": 0}], "summary": {"failed": 0}},
    )
    cases = [
        _case("acceptance_requirement_dropped", baseline, _drop_acceptance, "acceptance_not_tested"),
        _case("implementation_target_substituted", baseline, _substitute_implementation_target, "implementation_target_drift"),
        _case("test_target_substituted", baseline, _substitute_test_target, "test_target_mismatch"),
        _case("false_green_test_result", baseline, _false_green_result, "false_green_test_result"),
        _case("hidden_side_effect", baseline, _inject_hidden_side_effect, "forbidden_actions_clean"),
        _case("writable_scope_expanded", baseline, _expand_writable_scope, "implementation_writable_scope_expanded"),
    ]
    passed = sum(1 for case in cases if case["status"] == "passed")
    report = {
        "artifact_type": "ReviewerAdversarialTrialReport",
        "schema_version": "reviewer_adversarial_trial.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "ok" if passed == len(cases) else "needs_work",
        "summary": {"case_count": len(cases), "passed": passed, "failed": len(cases) - passed},
        "cases": cases,
        "invariants": {"source_code_changes": False, "registry_changes": False, "mutation_scope": "artifacts_in_memory_only"},
    }
    if write:
        out_dir = root / "artifacts" / "field_trials"
        out_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        path = out_dir / f"reviewer_adversarial_trial_{stamp}.json"
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        report["report_path"] = path.as_posix()
    return report


def _case(case_id: str, baseline: tuple[dict[str, Any], ...], mutate: Mutation, expected_code: str) -> dict[str, Any]:
    spec, plan, test_plan, test_result = deepcopy(baseline)
    mutate(spec, plan, test_plan, test_result)
    review = build_review_findings(technical_spec=spec, implementation_plan=plan, test_plan=test_plan, test_result=test_result)
    observed = {
        *(str(row.get("code")) for row in review.get("findings", []) if isinstance(row, dict)),
        *(str(row.get("code")) for row in review.get("contract_violations", []) if isinstance(row, dict)),
        *(str(row.get("code")) for row in review.get("architecture_drift", []) if isinstance(row, dict)),
        *(str(row.get("code")) for row in review.get("conformance_checks", []) if isinstance(row, dict) and not row.get("passed")),
    }
    detected = expected_code in observed and review.get("recommendation") == "request_rework"
    return {
        "case": case_id,
        "status": "passed" if detected else "failed",
        "expected_code": expected_code,
        "observed_codes": sorted(observed),
        "recommendation": review.get("recommendation"),
    }


def _drop_acceptance(spec: dict[str, Any], plan: dict[str, Any], test_plan: dict[str, Any], result: dict[str, Any]) -> None:
    spec.setdefault("acceptance_criteria", []).append({"id": "AC-MUTATED", "statement": "silently lost requirement"})


def _substitute_implementation_target(spec: dict[str, Any], plan: dict[str, Any], test_plan: dict[str, Any], result: dict[str, Any]) -> None:
    plan["implementation_target"]["candidate"] = "main.py:unsafe_substitute"
    plan["writable_scope"] = ["main.py:unsafe_substitute"]


def _substitute_test_target(spec: dict[str, Any], plan: dict[str, Any], test_plan: dict[str, Any], result: dict[str, Any]) -> None:
    test_plan["test_target"]["candidate"] = "main.py:untested_substitute"


def _false_green_result(spec: dict[str, Any], plan: dict[str, Any], test_plan: dict[str, Any], result: dict[str, Any]) -> None:
    result["commands"] = [{"status": "failed", "exit_code": 1}]
    result["summary"] = {"failed": 1}


def _inject_hidden_side_effect(spec: dict[str, Any], plan: dict[str, Any], test_plan: dict[str, Any], result: dict[str, Any]) -> None:
    plan["forbidden_actions_observed"] = ["network_execution"]


def _expand_writable_scope(spec: dict[str, Any], plan: dict[str, Any], test_plan: dict[str, Any], result: dict[str, Any]) -> None:
    plan["writable_scope"] = [*plan["writable_scope"], "main.py:write_output"]
