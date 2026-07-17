"""Schema-backed role artifact facade."""

from __future__ import annotations

from typing import Any

from .role_artifact_builder import build_configured_artifact
from .role_skill_common import RoleSkillError, load_skill_registry, write_role_artifact


def run_architect_skill(
    *,
    goal: str,
    project_report: dict[str, Any],
    constraints: list[str] | None = None,
    advisory_config: Any = None,
) -> dict[str, Any]:
    return build_configured_artifact(
        builder_id="architecture_decision_v1",
        goal=goal,
        project_report=project_report,
        constraints=constraints,
        advisory_config=advisory_config,
    )


def run_spec_writer_skill(*, architecture_decision: dict[str, Any]) -> dict[str, Any]:
    return build_configured_artifact(
        builder_id="technical_spec_v1",
        architecture_decision=architecture_decision,
    )


def run_implementer_skill(*, technical_spec: dict[str, Any]) -> dict[str, Any]:
    return build_configured_artifact(
        builder_id="implementation_plan_v1",
        technical_spec=technical_spec,
    )


def run_tester_skill(*, technical_spec: dict[str, Any], implementation_plan: dict[str, Any]) -> dict[str, Any]:
    return build_configured_artifact(
        builder_id="test_plan_v1",
        technical_spec=technical_spec,
        implementation_plan=implementation_plan,
    )


def run_reviewer_skill(
    *,
    technical_spec: dict[str, Any],
    implementation_plan: dict[str, Any],
    test_plan: dict[str, Any],
    test_result: dict[str, Any] | None = None,
    executable_acceptance_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return build_configured_artifact(
        builder_id="review_findings_v1",
        technical_spec=technical_spec,
        implementation_plan=implementation_plan,
        test_plan=test_plan,
        test_result=test_result,
        executable_acceptance_result=executable_acceptance_result,
    )


__all__ = [
    "RoleSkillError",
    "load_skill_registry",
    "run_architect_skill",
    "run_implementer_skill",
    "run_reviewer_skill",
    "run_spec_writer_skill",
    "run_tester_skill",
    "write_role_artifact",
]
