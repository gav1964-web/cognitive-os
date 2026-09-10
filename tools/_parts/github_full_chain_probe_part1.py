"""Run Project Analyzer -> Architect -> SpecWriter -> Implementer -> Tester -> Reviewer over GitHub projects."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.dont_write_bytecode = True

from runtime.configured_role_pipeline import artifact_by_type, producer_for_artifact_type, run_configured_role_prefix
from runtime.configured_execution_feedback import close_configured_execution_feedback
from runtime.programmer_executor import run_programmer_executor
from runtime.generated_stub_admission import inspect_generated_function_stubs
from runtime.framework_plugin_role_semantics import (
    artifact_digest,
    evaluate_framework_plugin_role_semantics,
)
from runtime.project_recognition import attach_project_recognition, recognize_project
from runtime.role_foundation_field_trial import _primary_language_scope
from runtime.role_project_analysis import analyze_role_project
from runtime.source_target_policy import is_context_only_implementation_target
from tools.github_full_chain_scoring import (
    CONTROLLED_BLOCK_SCORE,
    META_ONLY_SCORE_CAP,
    bounded_quality_score,
    is_controlled_block,
    executor_evidence_ready,
    quality_score as _quality_score,
    selected_target_quality,
    summary as _summary,
)
from tools.github_full_chain_checkpoint import run_case_batch
from tools.github_full_chain_case_runner import run_case_with_timeout
from tools.github_full_chain_report import markdown
from runtime.project_probe_env_policy import load_project_probe_env_policy


READY_THRESHOLD = 0.92


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--projects-dir", required=True)
    parser.add_argument("--label", default="github_full_chain_probe")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--run-executor", action="store_true")
    parser.add_argument("--run-verification", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--case-timeout-seconds", type=int)
    parser.add_argument("--project-name", action="append", default=[])
    args = parser.parse_args()
    root = Path(args.root).resolve()
    projects_dir = Path(args.projects_dir)
    if not projects_dir.is_absolute():
        projects_dir = root / projects_dir
    probe_policy = dict(load_project_probe_env_policy().get("field_trial") or {})
    report = run_probe(
        root=root,
        projects_dir=projects_dir.resolve(),
        label=args.label,
        run_executor=args.run_executor,
        run_verification=args.run_verification,
        checkpoint_path=root / "artifacts" / "field_trials" / f"{args.label}_checkpoint.json",
        resume=args.resume,
        progress=True,
        case_timeout_seconds=int(args.case_timeout_seconds or probe_policy.get("case_timeout_seconds") or 180),
        termination_grace_seconds=int(probe_policy.get("termination_grace_seconds") or 5),
        project_names=set(args.project_name) or None,
    )
    if args.write:
        report.update(write_report(root, report, args.label))
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] == "ok" else 1


def run_probe(
    *,
    root: Path,
    projects_dir: Path,
    label: str,
    run_executor: bool = False,
    run_verification: bool = False,
    checkpoint_path: Path | None = None,
    resume: bool = False,
    progress: bool = False,
    case_timeout_seconds: int = 0,
    termination_grace_seconds: int = 5,
    recognition_profile: dict[str, Any] | None = None,
    stop_outside_recognition_profile: bool = False,
    project_names: set[str] | None = None,
) -> dict[str, Any]:
    cases = run_case_batch(
        projects_dir=projects_dir,
        runner=lambda project: run_case_with_timeout(
            project, root=root, run_executor=run_executor, run_verification=run_verification,
            timeout_seconds=case_timeout_seconds, termination_grace_seconds=termination_grace_seconds,
            recognition_profile=recognition_profile,
            stop_outside_recognition_profile=stop_outside_recognition_profile,
        ) if case_timeout_seconds else _run_case(
            project, root=root, run_executor=run_executor, run_verification=run_verification,
            recognition_profile=recognition_profile,
            stop_outside_recognition_profile=stop_outside_recognition_profile,
        ),
        checkpoint_path=checkpoint_path,
        resume=resume,
        progress=progress,
        project_names=project_names,
    )
    scored = [case for case in cases if case["status"] != "out_of_scope"]
    worst_case = min((float(case["quality_score"]) for case in scored), default=0.0)
    ready_by_worst_case = bool(scored) and worst_case >= READY_THRESHOLD and not any(case["status"] == "needs_review" for case in scored)
    return {
        "artifact_type": "GitHubFullChainProbeReport",
        "schema_version": "github_full_chain_probe_report.v2",
        "status": "ok" if ready_by_worst_case and all(case["status"] in {"ok", "blocked_ok", "out_of_scope"} for case in cases) else "needs_review",
        "milestone": label,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "project_count": len(cases),
        "summary": _summary(cases, worst_case, ready_by_worst_case),
        "invariants": {
            "llm_invoked": False,
            "source_projects_modified": any(case["source_code_changes"] for case in cases),
            "registry_changes": False,
            "teacher_reference_is_ground_truth": False,
            "automatic_code_changes_from_own_output": False,
            "foundry_or_promote_not_in_scope": True,
            "execution_in_scope": run_executor,
            "run_verification": run_verification,
        },
        "cases": cases,
    }

