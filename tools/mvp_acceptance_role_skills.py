"""Role skill scenarios for MVP acceptance."""

from __future__ import annotations

import sys

import mvp_acceptance_checks as checks
from mvp_acceptance_report import AcceptanceReport


def role_skill_checks(report: AcceptanceReport) -> None:
    architect = report.command(
        "architect_role_skill",
        [
            sys.executable,
            "tools/role_skill_run.py",
            "--root",
            ".",
            "--role",
            "architect",
            "--goal",
            "Extract first safe capability",
            "--project-dir",
            "benchmarks/project_analyzer/projects/simple_cli_tool",
            "--write",
        ],
        layers=["L4"],
        check=checks.architect_role_skill_ok,
    )
    spec = report.command(
        "spec_writer_role_skill",
        [
            sys.executable,
            "tools/role_skill_run.py",
            "--root",
            ".",
            "--role",
            "spec_writer",
            "--adr",
            str(architect.get("artifact_path")),
            "--write",
        ],
        layers=["L4"],
        check=checks.spec_writer_role_skill_ok,
    )
    implementation = report.command(
        "implementer_role_skill",
        [
            sys.executable,
            "tools/role_skill_run.py",
            "--root",
            ".",
            "--role",
            "implementer",
            "--spec",
            str(spec.get("artifact_path")),
            "--write",
        ],
        layers=["L4"],
        check=checks.implementer_role_skill_ok,
    )
    test_plan = report.command(
        "tester_role_skill",
        [
            sys.executable,
            "tools/role_skill_run.py",
            "--root",
            ".",
            "--role",
            "tester",
            "--spec",
            str(spec.get("artifact_path")),
            "--plan",
            str(implementation.get("artifact_path")),
            "--write",
        ],
        layers=["L4"],
        check=checks.tester_role_skill_ok,
    )
    report.command(
        "reviewer_role_skill",
        [
            sys.executable,
            "tools/role_skill_run.py",
            "--root",
            ".",
            "--role",
            "reviewer",
            "--spec",
            str(spec.get("artifact_path")),
            "--plan",
            str(implementation.get("artifact_path")),
            "--test-plan",
            str(test_plan.get("artifact_path")),
            "--write",
        ],
        layers=["L4"],
        check=checks.reviewer_role_skill_ok,
    )
    report.command(
        "role_foundation_pipeline",
        [
            sys.executable,
            "tools/role_foundation_run.py",
            "--root",
            ".",
            "--benchmark",
            "--benchmark-project",
            "simple_cli_tool",
            "--write",
        ],
        layers=["L4"],
        check=checks.role_foundation_ok,
    )
    report.command(
        "role_artifact_quality",
        [sys.executable, "tools/role_artifact_quality.py", "--root", ".", "--write"],
        layers=["L4"],
        check=checks.json_status_ok,
    )
    report.command(
        "role_artifact_quality_external_3",
        [
            sys.executable,
            "tools/role_artifact_quality.py",
            "--root",
            ".",
            "--project-dir",
            "F:/ubuntu/test/map",
            "--project-dir",
            "F:/ubuntu/test/5",
            "--project-dir",
            "F:/ubuntu/test/004",
            "--write",
        ],
        layers=["L4"],
        check=checks.json_status_ok,
    )
    report.command(
        "role_artifact_quality_github_10",
        [
            sys.executable,
            "tools/role_artifact_quality.py",
            "--root",
            ".",
            "--benchmarks-dir",
            "benchmarks/github_full_trial_10",
            "--write",
        ],
        layers=["L4"],
        check=checks.json_status_ok,
    )
    report.command(
        "role_pipeline_orchestrator",
        [
            sys.executable,
            "tools/role_pipeline_run.py",
            "--root",
            ".",
            "--project-dir",
            "benchmarks/project_analyzer/projects/simple_cli_tool",
            "--goal",
            "Extract first safe capability",
            "--write",
        ],
        layers=["L4"],
        check=checks.role_pipeline_ok,
    )
    report.command(
        "role_pipeline_benchmark",
        [sys.executable, "tools/role_pipeline_benchmark.py", "--root", ".", "--write"],
        layers=["L4"],
        check=checks.role_pipeline_benchmark_ok,
    )
