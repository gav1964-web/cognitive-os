"""Run MVP acceptance scenarios and write a layer-oriented report."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

import mvp_acceptance_checks as checks
from mvp_acceptance_report import AcceptanceReport
from mvp_acceptance_role_skills import role_skill_checks
from mvp_acceptance_stage2 import stage2_checks
from mvp_acceptance_stage3 import stage3_checks


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--skip-pytest", action="store_true")
    parser.add_argument("--live-l4", action="store_true", help="Include the non-deterministic external L4 quality probe")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    report = AcceptanceReport(root)
    spec_id = "acceptance_echo"
    _cleanup_acceptance_foundry(root, spec_id)

    if not args.skip_pytest:
        report.command("all_tests", [sys.executable, "-m", "pytest"], layers=["all"], check=checks.returncode_ok)
    report.command(
        "compileall",
        [sys.executable, "-m", "compileall", "runtime", "tools", "plugins", "skills", "tests", "run_mvp.py"],
        layers=["all"],
        check=checks.returncode_ok,
    )
    report.command("plugin_contracts", [sys.executable, "tools/check_plugins.py", "--root", "."], layers=["L1"], check=checks.json_status_ok)
    report.command("registry_doctor", [sys.executable, "tools/registry_doctor.py", "--root", "."], layers=["L2.5"], check=checks.json_status_ok)

    _core_runtime_checks(report)
    _durable_queue_checks(report)
    _foundry_checks(report, root, spec_id)
    dialogue_id = _dialogue_checks(report)
    _memory_and_level4_checks(report, dialogue_id, live_l4=args.live_l4)

    final = report.finish()
    print(json.dumps(final, ensure_ascii=False, indent=2))
    return 0 if final["status"] == "ok" else 1


def _core_runtime_checks(report: AcceptanceReport) -> None:
    report.command(
        "mvp_happy_path",
        [sys.executable, "run_mvp.py", "--scenario", "happy", "--reset-registry"],
        layers=["L1", "L2"],
        check=checks.happy_path_ok,
    )
    report.command(
        "mvp_quarantine_fallback",
        [sys.executable, "run_mvp.py", "--scenario", "quarantine", "--reset-registry"],
        layers=["L3"],
        check=checks.quarantine_ok,
    )
    report.command(
        "mvp_no_fallback_stop",
        [sys.executable, "run_mvp.py", "--scenario", "no_fallback"],
        layers=["L3"],
        check=checks.controlled_stop_ok,
    )
    report.command(
        "restore_registry_after_no_fallback",
        [sys.executable, "run_mvp.py", "--scenario", "happy", "--reset-registry"],
        layers=["L2.5"],
        check=checks.happy_path_ok,
    )


def _durable_queue_checks(report: AcceptanceReport) -> None:
    queue_input = json.dumps({"url": "mock://ok", "output_path": "artifacts/outputs/acceptance_queue.json"})
    enqueue = report.command(
        "durable_queue_enqueue",
        [
            sys.executable,
            "tools/enqueue_pipeline.py",
            "--root",
            ".",
            "--pipeline",
            "pipelines/fetch_parse_save.json",
            "--input-json",
            queue_input,
            "--reset-registry",
            "--priority",
            "10",
        ],
        layers=["L2"],
        check=checks.json_status_queued,
    )
    report.command(
        "durable_worker_pool",
        [sys.executable, "tools/run_worker_pool.py", "--root", ".", "--workers", "2", "--max-jobs", "1"],
        layers=["L2"],
        check=checks.worker_pool_ok,
    )
    report.command(
        "durable_queue_status",
        [sys.executable, "tools/queue_status.py", "--root", "."],
        layers=["L2"],
        check=checks.queue_has_completed(enqueue.get("job_id")),
    )


def _foundry_checks(report: AcceptanceReport, root: Path, spec_id: str) -> None:
    report.command(
        "foundry_generate_spec",
        [
            sys.executable,
            "tools/generate_capability_spec.py",
            "--root",
            ".",
            "--id",
            spec_id,
            "--purpose",
            "Echo a string value for MVP acceptance.",
            "--force",
        ],
        layers=["L3.2"],
        check=checks.json_status_created,
    )
    report.command(
        "foundry_validate_spec",
        [sys.executable, "tools/validate_capability_spec.py", "--spec", f"generated/specs/{spec_id}.json"],
        layers=["L3.2"],
        check=checks.json_status_ok,
    )
    report.command(
        "foundry_generate_candidate",
        [sys.executable, "tools/generate_plugin_candidate.py", "--root", ".", "--id", spec_id, "--force"],
        layers=["L3.2"],
        check=checks.json_status_created,
    )
    report.command(
        "foundry_dry_run_promotion",
        [sys.executable, "tools/promote_candidate.py", "--root", ".", "--id", spec_id, "--dry-run"],
        layers=["L3.2"],
        check=checks.json_status("dry_run_passed"),
    )
    _cleanup_acceptance_foundry(root, spec_id)


def _dialogue_checks(report: AcceptanceReport) -> str:
    dialogue = report.command(
        "dialogue_create",
        [
            sys.executable,
            "tools/dialogue_memory.py",
            "--root",
            ".",
            "create",
            "--title",
            "Acceptance dialogue",
            "--topic",
            "runtime-memory",
        ],
        layers=["dialogue"],
        check=checks.json_status_created,
    )
    dialogue_id = str(dialogue.get("dialogue_id"))
    report.command(
        "dialogue_note_recall",
        [
            sys.executable,
            "tools/dialogue_memory.py",
            "--root",
            ".",
            "note",
            "--kind",
            "principle",
            "--topic",
            "runtime-memory",
            "--dialogue-id",
            dialogue_id,
            "--text",
            "Dialog memory provides context hints but does not execute plugins or mutate registry.",
        ],
        layers=["dialogue"],
        check=checks.json_status_ok,
    )
    report.command(
        "dialogue_turn",
        [
            sys.executable,
            "tools/dialogue_memory.py",
            "--root",
            ".",
            "turn",
            "--dialogue-id",
            dialogue_id,
            "--role",
            "user",
            "--text",
            "Remember that dialogue memory is contextual and separate from runtime memory.",
        ],
        layers=["dialogue"],
        check=checks.json_status_ok,
    )
    report.command(
        "dialogue_recall",
        [sys.executable, "tools/dialogue_memory.py", "--root", ".", "recall", "--query", "dialog memory context registry plugins"],
        layers=["dialogue"],
        check=checks.dialogue_recall_ok,
    )
    report.command(
        "dialogue_compact",
        [sys.executable, "tools/dialogue_memory.py", "--root", ".", "compact", "--dialogue-id", dialogue_id, "--keep-recent-turns", "1"],
        layers=["dialogue"],
        check=checks.dialogue_compact_ok,
    )
    report.command(
        "dialogue_topic_graph",
        [sys.executable, "tools/dialogue_memory.py", "--root", ".", "topic-graph", "--rebuild"],
        layers=["dialogue"],
        check=checks.dialogue_topic_graph_ok,
    )
    return dialogue_id


def _memory_and_level4_checks(report: AcceptanceReport, dialogue_id: str, *, live_l4: bool = False) -> None:
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
                os.environ.get("COGNITIVE_OS_L4_BASE_URL", "http://127.0.0.1:8000/v1"),
                "--l4-model",
                os.environ.get("COGNITIVE_OS_L4_MODEL", "gpt-4.1"),
                "--context",
                os.environ.get("COGNITIVE_OS_L4_CONTEXT", "compact"),
                "--write",
            ],
            layers=["L4"],
            check=checks.l4_quality_probe_ok,
        )
    role_skill_checks(report)
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


def _cleanup_acceptance_foundry(root: Path, spec_id: str) -> None:
    candidate_dir = root / "generated" / "candidates" / spec_id
    spec_path = root / "generated" / "specs" / f"{spec_id}.json"
    if candidate_dir.exists():
        shutil.rmtree(candidate_dir)
    if spec_path.exists():
        spec_path.unlink()


if __name__ == "__main__":
    raise SystemExit(main())
