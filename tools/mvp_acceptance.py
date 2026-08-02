"""Run MVP acceptance scenarios and write a layer-oriented report."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

import mvp_acceptance_checks as checks
from mvp_acceptance_report import AcceptanceReport
from mvp_acceptance_l4 import memory_and_level4_checks


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--skip-pytest", action="store_true")
    parser.add_argument("--live-l4", action="store_true", help="Include the non-deterministic external L4 quality probe")
    parser.add_argument("--local-project-trials", action="store_true", help="Include Local-3 projects outside the repository")
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
    report.command("repo_lint", [sys.executable, "tools/check_repo_lint.py", "--root", "."], layers=["all"], check=checks.json_status_ok)
    report.command("plugin_contracts", [sys.executable, "tools/check_plugins.py", "--root", "."], layers=["L1"], check=checks.json_status_ok)
    report.command("registry_doctor", [sys.executable, "tools/registry_doctor.py", "--root", "."], layers=["L2.5"], check=checks.json_status_ok)

    _core_runtime_checks(report)
    _durable_queue_checks(report)
    _foundry_checks(report, root, spec_id)
    dialogue_id = _dialogue_checks(report)
    memory_and_level4_checks(
        report,
        dialogue_id,
        live_l4=args.live_l4,
        local_project_trials=args.local_project_trials,
    )

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








def _cleanup_acceptance_foundry(root: Path, spec_id: str) -> None:
    candidate_dir = root / "generated" / "candidates" / spec_id
    spec_path = root / "generated" / "specs" / f"{spec_id}.json"
    if candidate_dir.exists():
        shutil.rmtree(candidate_dir)
    if spec_path.exists():
        spec_path.unlink()


if __name__ == "__main__":
    raise SystemExit(main())
