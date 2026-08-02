from __future__ import annotations
import json
from pathlib import Path
import pytest
from runtime.project_benchmark import analyze_project
from runtime.local_inference import LocalInferenceConfig
from runtime.greenfield_role_pipeline import run_greenfield_role_pipeline
from runtime.role_artifact_quality import evaluate_implementation_plan
from runtime.role_skills import run_role_skill
ROOT = Path(__file__).resolve().parents[2]
def _run(role_id: str, **inputs):
    return run_role_skill(role_id, **inputs)

def test_reviewer_skill_returns_review_findings():
    project_dir = ROOT / "benchmarks" / "project_analyzer" / "projects" / "simple_cli_tool"
    report = analyze_project(project_dir)["project_map_report"]
    adr = _run("architect", goal="Extract first safe capability", project_report=report)
    spec = _run("spec_writer", architecture_decision=adr)
    implementation = _run("implementer", technical_spec=spec)
    test_plan = _run("tester", technical_spec=spec, implementation_plan=implementation)

    review = _run(
        "reviewer",
        technical_spec=spec,
        implementation_plan=implementation,
        test_plan=test_plan,
        test_result={"status": "ok", "executable_acceptance_result": {"status": "passed"}},
    )

    assert review["artifact_type"] == "ReviewFindings"
    assert review["role"] == "reviewer"
    assert review["status"] == "ok"
    assert review["findings"]
    assert review["review_target"]["candidate"] == implementation["implementation_target"]["candidate"]
    assert review["coverage_assessment"]["target_covered"] is True
    assert review["coverage_assessment"]["contract_matrix_rows"] > 0
    assert review["conformance_status"] == "passed"
    assert all(row["passed"] for row in review["conformance_checks"])
    assert review["risk_assessment"]
    assert review["contract_violations"] == []
    assert review["recommendation"] in {"approve", "approve_with_risks", "request_rework"}
    assert review["forbidden_actions_observed"] == []


def test_reviewer_rejects_writable_scope_expansion():
    project_dir = ROOT / "benchmarks" / "project_analyzer" / "projects" / "simple_cli_tool"
    report = analyze_project(project_dir)["project_map_report"]
    adr = _run("architect", goal="Extract first safe capability", project_report=report)
    spec = _run("spec_writer", architecture_decision=adr)
    implementation = _run("implementer", technical_spec=spec)
    test_plan = _run("tester", technical_spec=spec, implementation_plan=implementation)
    test_plan["test_strategy"]["writable_scope"] = implementation["evidence_scope"]

    review = _run(
        "reviewer",
        technical_spec=spec,
        implementation_plan=implementation,
        test_plan=test_plan,
        test_result={"status": "ok"},
    )

    assert review["recommendation"] == "request_rework"
    assert review["conformance_status"] == "failed"
    assert any(row["code"] == "test_writable_scope_mismatch" for row in review["contract_violations"])


def test_reviewer_rejects_failed_executable_acceptance_result():
    project_dir = ROOT / "benchmarks" / "project_analyzer" / "projects" / "simple_cli_tool"
    report = analyze_project(project_dir)["project_map_report"]
    adr = _run("architect", goal="Extract first safe capability", project_report=report)
    spec = _run("spec_writer", architecture_decision=adr)
    implementation = _run("implementer", technical_spec=spec)
    test_plan = _run("tester", technical_spec=spec, implementation_plan=implementation)

    review = _run(
        "reviewer",
        technical_spec=spec,
        implementation_plan=implementation,
        test_plan=test_plan,
        test_result={"status": "failed", "executable_acceptance_result": {"status": "failed"}},
    )

    assert review["recommendation"] == "request_rework"
    assert review["conformance_status"] == "failed"
    assert any(row["code"] == "executable_acceptance_passed_or_absent" and not row["passed"] for row in review["conformance_checks"])


def test_reviewer_does_not_turn_residual_risks_into_rework_when_conformant():
    project_dir = ROOT / "benchmarks" / "project_analyzer" / "projects" / "scraper_with_retry_and_cache"
    report = analyze_project(project_dir)["project_map_report"]
    adr = _run("architect", goal="Extract first safe capability", project_report=report)
    spec = _run("spec_writer", architecture_decision=adr)
    implementation = _run("implementer", technical_spec=spec)
    test_plan = _run("tester", technical_spec=spec, implementation_plan=implementation)

    review = _run(
        "reviewer",
        technical_spec=spec,
        implementation_plan=implementation,
        test_plan=test_plan,
        test_result={"status": "ok"},
    )

    assert review["recommendation"] == "approve_with_risks"
    assert review["conformance_status"] == "passed"
    assert review["contract_violations"] == []
    assert review["architecture_drift"] == []
    assert review["rework_tasks"] == []


def test_architect_skill_runs_on_benchmark_corpus():
    projects = sorted((ROOT / "benchmarks" / "project_analyzer" / "projects").iterdir())

    for project_dir in projects:
        if not project_dir.is_dir():
            continue
        report = analyze_project(project_dir)["project_map_report"]
        artifact = _run("architect", goal=f"Assess {project_dir.name}", project_report=report)
        assert artifact["status"] == "ok", project_dir.name
        assert artifact["chosen_option"]["id"], project_dir.name
        assert artifact["spec_writer_brief"]["scope"], project_dir.name
