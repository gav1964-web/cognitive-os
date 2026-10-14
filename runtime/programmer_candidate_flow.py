"""Candidate and repair flow helpers for the sandbox Programmer Executor."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .programmer_repair_strategy import build_patch_repair_strategy
from .programmer_sandbox_candidate import apply_sandbox_patch_candidate


def prepare_candidate_synthesis(
    *,
    execution_dir: Path,
    project_dir: Path,
    implementation_plan: dict[str, Any],
    synthesis: dict[str, Any],
    strategy: dict[str, Any],
) -> tuple[dict[str, Any], Path, dict[str, Any]]:
    attempt = {"status": "not_attempted", "reason": "deterministic_synthesis_available"}
    if synthesis.get("status") == "prepared":
        return synthesis, Path(str(synthesis.get("sandbox_project") or project_dir)), attempt
    attempt = apply_sandbox_patch_candidate(
        execution_dir=execution_dir, project_dir=project_dir, implementation_plan=implementation_plan, strategy=strategy
    )
    if attempt.get("status") != "applied_in_sandbox":
        return synthesis, Path(str(synthesis.get("sandbox_project") or project_dir)), attempt
    repaired_synthesis = _candidate_synthesis(attempt)
    return repaired_synthesis, Path(str(repaired_synthesis.get("sandbox_project") or project_dir)), attempt


def prepare_repair_synthesis(
    *,
    execution_dir: Path,
    project_dir: Path,
    implementation_plan: dict[str, Any],
    test_plan: dict[str, Any],
    test_result: dict[str, Any],
    sandbox_name: str = "llm_repair_sandbox",
) -> tuple[dict[str, Any], Path, dict[str, Any], dict[str, Any]]:
    strategy = build_patch_repair_strategy(
        project_dir=project_dir,
        implementation_plan=implementation_plan,
        test_plan=test_plan,
        test_result=test_result,
    )
    attempt = apply_sandbox_patch_candidate(
        execution_dir=execution_dir,
        project_dir=project_dir,
        implementation_plan=implementation_plan,
        strategy=strategy,
        sandbox_name=sandbox_name,
    )
    synthesis = _candidate_synthesis(attempt) if attempt.get("status") == "applied_in_sandbox" else {}
    return synthesis, Path(str(synthesis.get("sandbox_project") or project_dir)), strategy, attempt


def _candidate_synthesis(attempt: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": "prepared",
        "reason": str(attempt.get("reason") or "llm_patch_candidate_applied_in_sandbox"),
        "sandbox_project": attempt.get("sandbox_project"),
        "patches": attempt.get("patches", []),
    }
