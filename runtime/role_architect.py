"""Compatibility wrapper for ArchitectureDecisionRecord artifact generation."""

from __future__ import annotations

from typing import Any

from .architecture_decision_builder import build_architecture_decision
from .local_inference import LocalInferenceConfig


def run_architect_skill(
    *,
    goal: str,
    project_report: dict[str, Any],
    constraints: list[str] | None = None,
    advisory_config: LocalInferenceConfig | None = None,
) -> dict[str, Any]:
    return build_architecture_decision(
        goal=goal,
        project_report=project_report,
        role_id="architect",
        next_role_id="spec_writer",
        constraints=constraints,
        advisory_config=advisory_config,
    )
