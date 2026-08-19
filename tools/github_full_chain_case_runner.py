"""Run one full-chain case in a killable subprocess."""

from __future__ import annotations

import multiprocessing
import queue
import time
from pathlib import Path
from typing import Any


def run_case_with_timeout(
    project: Path,
    *,
    root: Path,
    run_executor: bool,
    run_verification: bool,
    timeout_seconds: int,
    termination_grace_seconds: int = 5,
) -> dict[str, Any]:
    context = multiprocessing.get_context("spawn")
    output = context.Queue(maxsize=1)
    process = context.Process(
        target=_case_worker,
        args=(output, project, root, run_executor, run_verification),
        daemon=False,
    )
    process.start()
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            result = output.get(timeout=min(0.2, max(deadline - time.monotonic(), 0.01)))
            process.join(timeout=termination_grace_seconds)
            return dict(result)
        except queue.Empty:
            if not process.is_alive():
                process.join(timeout=termination_grace_seconds)
                return _timeout_case(project, "evaluation_case_process_exited_without_result")
    process.terminate()
    process.join(timeout=termination_grace_seconds)
    if process.is_alive():
        process.kill()
        process.join(timeout=termination_grace_seconds)
    return _timeout_case(project, f"evaluation_case_timeout_after_{timeout_seconds}_seconds")


def _case_worker(
    output: Any, project: Path, root: Path, run_executor: bool, run_verification: bool
) -> None:
    from tools.github_full_chain_probe import _run_case

    try:
        result = _run_case(
            project,
            root=root,
            run_executor=run_executor,
            run_verification=run_verification,
        )
    except BaseException as exc:  # noqa: BLE001 - child failure becomes field evidence.
        result = _timeout_case(project, f"{type(exc).__name__}: {exc}"[:1000])
    output.put(result)


def _timeout_case(project: Path, error: str) -> dict[str, Any]:
    return {
        "project": project.name,
        "project_dir": project.as_posix(),
        "status": "needs_review",
        "quality_score": 0.0,
        "selected_target_quality": {"score": 0.0},
        "target_chain": {},
        "contract_violations": 0,
        "architecture_drift": 0,
        "forbidden_sources": [],
        "source_code_changes": False,
        "llm_invoked": False,
        "executor": {"executor_status": "evaluation_timeout"},
        "failed_checks": [{"code": "evaluation_case_timeout", "passed": False}],
        "evaluation_error": error,
    }
