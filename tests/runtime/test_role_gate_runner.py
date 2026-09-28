from __future__ import annotations

from pathlib import Path

from runtime.project_benchmark import analyze_project
from runtime.role_artifact_interpreter import run_role_artifact_pipeline
from runtime.role_gate_runner import run_role_gate_report
from runtime.role_pipeline import run_role_pipeline


ROOT = Path(__file__).resolve().parents[2]


def test_role_gate_runner_executes_directory_gates():
    project_dir = ROOT / "benchmarks" / "project_analyzer" / "projects" / "simple_cli_tool"
    project_report = analyze_project(project_dir)["project_map_report"]
    artifacts = run_role_artifact_pipeline(goal="Extract first safe capability", project_report=project_report)

    report = run_role_gate_report(artifacts=artifacts, project_report=project_report)

    assert report["artifact_type"] == "RoleGateReport"
    assert report["status"] == "ok"
    assert report["summary"]["checked"] >= 6
    assert report["summary"]["failed"] == 0
    assert all(case["gates"] for case in report["cases"] if case["status"] != "skipped")


def test_role_gate_modes_control_blocking_behavior():
    directory = {
        "schema_version": "role_directory.v2",
        "roles": {
            "architect": {
                "order": 1,
                "gates": ["unknown_check_for_test"],
                "quality_criteria": [],
                "fallback_policy": {},
            }
        },
    }
    artifacts = {"architecture_decision": {"artifact_type": "ArchitectureDecisionRecord", "role": "architect"}}

    advisory = run_role_gate_report(artifacts=artifacts, directory=directory, mode="advisory")
    strict = run_role_gate_report(artifacts=artifacts, directory=directory, mode="strict")
    release_required = run_role_gate_report(artifacts=artifacts, directory=directory, mode="release_required")

    assert advisory["status"] == "warning"
    assert advisory["summary"]["blocking_failed"] == 0
    assert strict["status"] == "failed"
    assert strict["summary"]["blocking_failed"] == 1
    assert release_required["status"] == "failed"
    assert release_required["blocking_policy"]["release_requires_clean_role_gates"] is True


def test_role_pipeline_includes_role_gate_report():
    project_dir = ROOT / "benchmarks" / "project_analyzer" / "projects" / "simple_cli_tool"

    result = run_role_pipeline(root=ROOT, project_dir=project_dir, goal="Extract first safe capability")

    assert result["status"] == "ok"
    assert result["role_gates"]["artifact_type"] == "RoleGateReport"
    assert result["role_gates"]["status"] == "ok"
