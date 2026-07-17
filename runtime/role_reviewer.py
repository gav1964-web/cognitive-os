"""Compatibility wrapper for ReviewFindings artifact generation."""

from __future__ import annotations

from typing import Any

from .review_findings_builder import build_review_findings


def run_reviewer_skill(
    *,
    technical_spec: dict[str, Any],
    implementation_plan: dict[str, Any],
    test_plan: dict[str, Any],
    test_result: dict[str, Any] | None = None,
    executable_acceptance_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return build_review_findings(
        technical_spec=technical_spec,
        implementation_plan=implementation_plan,
        test_plan=test_plan,
        role_id="reviewer",
        test_result=test_result,
        executable_acceptance_result=executable_acceptance_result,
    )
