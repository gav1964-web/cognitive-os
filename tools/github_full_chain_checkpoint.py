"""Checkpointed case execution for long full-chain field trials."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any, Callable


def run_case_batch(
    *,
    projects_dir: Path,
    runner: Callable[[Path], dict[str, Any]],
    checkpoint_path: Path | None = None,
    resume: bool = False,
    progress: bool = False,
) -> list[dict[str, Any]]:
    projects = sorted(path for path in projects_dir.iterdir() if (path / ".git").exists())
    completed = _completed_cases(checkpoint_path) if resume else {}
    cases: list[dict[str, Any]] = []
    for index, project in enumerate(projects, 1):
        if project.name in completed:
            case = completed[project.name]
            state = "resumed"
        else:
            started = time.monotonic()
            try:
                case = dict(runner(project))
            except Exception as exc:
                case = _error_case(project, exc)
            case["elapsed_seconds"] = round(time.monotonic() - started, 3)
            state = str(case.get("status") or "unknown")
        cases.append(case)
        if checkpoint_path is not None:
            _write_checkpoint(checkpoint_path, cases, len(projects))
        if progress:
            print(f"[{index}/{len(projects)}] {project.name}: {state}", file=sys.stderr, flush=True)
    return cases


def _completed_cases(path: Path | None) -> dict[str, dict[str, Any]]:
    if path is None or not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return {
        str(case.get("project") or ""): dict(case)
        for case in payload.get("cases", [])
        if isinstance(case, dict) and case.get("project")
    }


def _write_checkpoint(path: Path, cases: list[dict[str, Any]], project_count: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "artifact_type": "GitHubFullChainCheckpoint",
        "project_count": project_count,
        "completed_count": len(cases),
        "cases": cases,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _error_case(project: Path, exc: Exception) -> dict[str, Any]:
    return {
        "project": project.name,
        "project_dir": project.as_posix(),
        "status": "needs_review",
        "quality_score": 0.0,
        "selected_target_quality": {"score": 0.0},
        "contract_violations": 0,
        "architecture_drift": 0,
        "forbidden_sources": [],
        "source_code_changes": False,
        "llm_invoked": False,
        "executor": {"executor_status": "evaluation_error"},
        "failed_checks": [{"code": "evaluation_case_exception", "passed": False}],
        "evaluation_error": f"{type(exc).__name__}: {exc}"[:1000],
    }
