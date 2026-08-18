"""Bounded verify-and-repair loop for sandbox Programmer candidates."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from .programmer_acceptance_gate import enforce_prepared_patch_acceptance
from .programmer_candidate_flow import prepare_repair_synthesis
from .programmer_verification import run_test_result


def run_bounded_repairs(
    *,
    root: Path,
    source_project_dir: Path,
    execution_project_dir: Path,
    execution_dir: Path,
    implementation_plan: dict[str, Any],
    test_plan: dict[str, Any],
    test_result: dict[str, Any],
    synthesis: dict[str, Any],
    candidate_attempt: dict[str, Any],
    run_verification: bool,
    max_commands: int,
    should_repair: Callable[[dict[str, Any], dict[str, Any], dict[str, Any]], bool],
    max_attempts: int = 2,
) -> dict[str, Any]:
    strategies: list[dict[str, Any]] = []
    attempts: list[dict[str, Any]] = []
    trigger_attempt = candidate_attempt
    for index in range(1, max_attempts + 1):
        if not should_repair(test_result, trigger_attempt, implementation_plan):
            break
        synthesis, execution_project_dir, strategy, attempt = prepare_repair_synthesis(
            execution_dir=execution_dir,
            project_dir=execution_project_dir,
            implementation_plan=implementation_plan,
            test_plan=test_plan,
            test_result=test_result,
            sandbox_name=f"llm_repair_sandbox_{index}",
        )
        strategies.append(strategy)
        attempts.append(attempt)
        trigger_attempt = attempt
        if attempt.get("status") != "applied_in_sandbox":
            break
        test_result = run_test_result(
            root=root,
            project_dir=execution_project_dir,
            source_project_dir=source_project_dir,
            implementation_plan=implementation_plan,
            test_plan=test_plan,
            execution_dir=execution_dir,
            run_verification=run_verification,
            max_commands=max_commands,
        )
        enforce_prepared_patch_acceptance(test_result, synthesis, implementation_plan)
    return {
        "synthesis": synthesis,
        "execution_project_dir": execution_project_dir,
        "test_result": test_result,
        "repair_strategies": strategies,
        "repair_attempts": attempts,
    }
