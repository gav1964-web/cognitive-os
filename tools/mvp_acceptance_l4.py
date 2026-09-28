"""L4, memory and product-layer MVP acceptance scenarios."""

from __future__ import annotations

import json
import os
import sys

import mvp_acceptance_checks as checks
from mvp_acceptance_report import AcceptanceReport
from mvp_acceptance_role_skills import role_skill_checks
from mvp_acceptance_stage2 import stage2_checks
from mvp_acceptance_stage3 import stage3_checks

try:
    from tools.l4_defaults import DEFAULT_L4_BASE_URL, DEFAULT_L4_MODEL
except ModuleNotFoundError:
    from l4_defaults import DEFAULT_L4_BASE_URL, DEFAULT_L4_MODEL

def memory_and_level4_checks(
    report: AcceptanceReport,
    dialogue_id: str,
    *,
    live_l4: bool = False,
    local_project_trials: bool = False,
) -> None:
    goal = "Normalize input text from $input.text and then hash the normalized text."
    for seed_number in (1, 2):
        report.command(
            f"memory_seed_run_{seed_number}",
            _goal_run_command(goal, dialogue_id, text=f"acceptance memory seed {seed_number}"),
            layers=["L4", "L3.5", "L2", "memory"],
            check=checks.goal_run_planner_in({"deterministic_required_capabilities", "memory_template"}),
        )
    report.command(
        "memory_templates",
        [sys.executable, "tools/memory_templates.py", "--root", ".", "--rebuild", "--min-support", "2"],
        layers=["memory"],
        check=checks.memory_template_mature,
    )
    report.command(
        "memory_instantiate",
        [sys.executable, "tools/memory_instantiate.py", "--root", ".", "--goal", goal, "--rebuild"],
        layers=["memory", "L3.5"],
        check=checks.planner_is_memory_template,
    )
    report.command(
        "level4_goal_run",
        _goal_run_command(goal, dialogue_id, text="acceptance layer check"),
        layers=["L4", "L3.5", "L2", "memory"],
        check=checks.goal_run_ok,
    )
    _level4_goal_checks(report)
    report.command(
        "field_trial_report",
        [sys.executable, "tools/field_trial_report.py", "--root", ".", "--limit", "10", "--write"],
        layers=["L4", "memory", "dialogue"],
        check=checks.json_status_ok,
    )
    report.command(
        "knowledge_gap_probe",
        [sys.executable, "tools/knowledge_gap_probe.py"],
        layers=["L1", "L3.5", "L4"],
        check=checks.json_status_ok,
    )
    report.command(
        "spinal_benchmark",
        [sys.executable, "tools/spinal_benchmark.py", "--root", ".", "--write"],
        layers=["L3.5", "L2"],
        check=checks.spinal_benchmark_ok,
    )
    report.command(
        "project_analyzer_benchmark",
        [sys.executable, "tools/project_analyzer_benchmark.py", "--root", ".", "--write"],
        layers=["L1", "L3.5", "L4"],
        check=checks.project_analyzer_benchmark_ok,
    )
    report.command(
        "l45_semantic_benchmark",
        [sys.executable, "tools/l45_semantic_benchmark.py", "--root", ".", "--write"],
        layers=["L4"],
        check=checks.json_status_ok,
    )
    if live_l4:
        report.command(
            "github_l4_quality_probe",
            [
                sys.executable,
                "tools/github_l4_interpretation_probe.py",
                "--root",
                ".",
                "--projects-dir",
                "benchmarks/github_full_trial_10",
                "--l4-base-url",
                os.environ.get("COGNITIVE_OS_L4_BASE_URL", DEFAULT_L4_BASE_URL),
                "--l4-model",
                os.environ.get("COGNITIVE_OS_L4_MODEL", DEFAULT_L4_MODEL),
                "--context",
                os.environ.get("COGNITIVE_OS_L4_CONTEXT", "compact"),
                "--write",
            ],
            layers=["L4"],
            check=checks.l4_quality_probe_ok,
        )
    role_skill_checks(report, local_project_trials=local_project_trials)
    report.command(
        "spec_writer_curriculum_local_3",
        [sys.executable, "tools/spec_writer_curriculum.py", "--root", ".", "--write"],
        layers=["L4"],
        check=checks.spec_writer_curriculum_ok,
    )
    report.command(
        "implementer_curriculum_local_3",
        [sys.executable, "tools/implementer_curriculum.py", "--root", ".", "--write"],
        layers=["L4"],
        check=checks.implementer_curriculum_ok,
    )
    report.command(
        "tester_curriculum_local_3",
        [sys.executable, "tools/tester_curriculum.py", "--root", ".", "--write"],
        layers=["L4"],
        check=checks.tester_curriculum_ok,
    )
    report.command(
        "reviewer_curriculum_local_3",
        [sys.executable, "tools/reviewer_curriculum.py", "--root", ".", "--write"],
        layers=["L4"],
        check=checks.reviewer_curriculum_ok,
    )
    stage2_checks(report)
    stage3_checks(report)
    report.command(
        "project_change_trial_probe",
        [sys.executable, "tools/project_change_trial_probe.py", "--root", ".", "--write"],
        layers=["L4"],
        check=checks.json_status_ok,
    )
    report.command(
        "project_change_patch_package_probe",
        [
            sys.executable,
            "tools/project_change_trial_run.py",
            "--root",
            ".",
            "--scenario",
            "benchmarks/project_change_trials/gigachat_patch_package_probe/scenario.json",
            "--write",
        ],
        layers=["L4"],
        check=checks.json_status_ok,
    )
    report.command(
        "project_extraction_proposal",
        [
            sys.executable,
            "tools/project_extraction_proposal.py",
            "--root",
            ".",
            "--project-dir",
            "benchmarks/project_analyzer/projects/simple_cli_tool",
            "--write",
            "--write-spec",
        ],
        layers=["L4", "L3.2"],
        check=checks.extraction_proposal_ok,
    )
    report.command(
        "project_transform_flow",
        [
            sys.executable,
            "tools/project_transform.py",
            "--root",
            ".",
            "--project-dir",
            "benchmarks/project_analyzer/projects/simple_cli_tool",
            "--force",
        ],
        layers=["L4", "L3.2"],
        check=checks.project_transform_ok,
    )

def _goal_run_command(goal: str, dialogue_id: str, *, text: str) -> list[str]:
    return [
        sys.executable,
        "tools/goal_run.py",
        "--root",
        ".",
        "--goal",
        goal,
        "--execute",
        "--dialogue-id",
        dialogue_id,
        "--input-json",
        json.dumps({"text": text}),
    ]

def _level4_goal_checks(report: AcceptanceReport) -> None:
    expected = {"memory_template", "deterministic_required_capabilities"}
    scenarios = [
        ("level4_list_files", "List files from $input.path", {"path": "plugins"}, ["L4", "L3.5", "L2"]),
        (
            "level4_markdown_to_text_file",
            "Convert markdown file from $input.input_path to plain text file at $input.output_path",
            {"input_path": "MVP_RUNTIME_SPEC.md", "output_path": "artifacts/outputs/acceptance_markdown.txt"},
            ["L4", "L3.5", "L2"],
        ),
        ("level4_fetch_links", "Fetch links from HTML URL at $input.url", {"url": "mock://ok"}, ["L4", "L3.5", "L2"]),
        ("level4_translate_text", "Translate input text from $input.text to German", {"text": "hello"}, ["L4", "L3.5", "L2", "L3.2"]),
        (
            "level4_parse_pdf",
            "Parse a PDF file from $input.path",
            {"path": "plugins/parse_pdf/tests/fixtures/sample.pdf"},
            ["L4", "L3.5", "L2", "L3.2"],
        ),
    ]
    for name, goal, input_payload, layers in scenarios:
        report.command(
            name,
            [
                sys.executable,
                "tools/goal_run.py",
                "--root",
                ".",
                "--goal",
                goal,
                "--execute",
                "--input-json",
                json.dumps(input_payload),
            ],
            layers=layers,
            check=checks.goal_run_planner_in(expected),
        )
