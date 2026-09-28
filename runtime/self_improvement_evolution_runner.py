"""Foundation-pipeline adapter for config evolution trials."""

from __future__ import annotations

from contextlib import nullcontext
from pathlib import Path
from typing import Any

from .executable_acceptance_policy import temporary_executable_acceptance_policy
from .self_improvement_evolution import proposal_from_diagnosis, run_config_evolution
from .self_improvement_training import _evaluate, _failure_packet, _source_fingerprint


def evolve_foundation_policy(
    *,
    root: Path,
    project_dir: Path,
    regression_projects: list[Path],
    proposal: dict[str, Any],
    target_score: float = 9.7,
    promote: bool = False,
) -> dict[str, Any]:
    baseline = _evaluate(root, project_dir, write=True)
    failure_packet = _failure_packet(baseline, target_score)

    return run_config_evolution(
        root=root,
        failure_packet=failure_packet,
        proposal=proposal,
        shadow_case=project_dir,
        regression_cases=regression_projects,
        evaluate=_foundation_evaluator(root),
        promote=promote,
    )


def evolve_diagnosed_foundation_policy(
    *,
    root: Path,
    project_dir: Path,
    failure_packet: dict[str, Any],
    diagnosis: dict[str, Any],
    regression_projects: list[Path],
    promote: bool = False,
) -> dict[str, Any] | None:
    proposal = proposal_from_diagnosis(diagnosis)
    if proposal is None:
        return None
    if not regression_projects:
        return {"status": "blocked", "decision": "regression_projects_required"}
    return run_config_evolution(
        root=root,
        failure_packet=failure_packet,
        proposal=proposal,
        shadow_case=project_dir,
        regression_cases=regression_projects,
        evaluate=_foundation_evaluator(root),
        promote=promote,
    )


def _foundation_evaluator(root: Path):
    def evaluate(candidate: dict[str, Any] | None, case: Any) -> dict[str, Any]:
        project = Path(case)
        before = _source_fingerprint(project)
        context = temporary_executable_acceptance_policy(candidate) if candidate else nullcontext()
        with context:
            result = _evaluate(root, project, write=True)
        result["source_project_unchanged"] = _source_fingerprint(project) == before
        return result

    return evaluate
