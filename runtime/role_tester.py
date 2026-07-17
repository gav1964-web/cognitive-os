"""Compatibility wrapper for TestPlan artifact generation."""

from __future__ import annotations

from typing import Any

from .test_plan_builder import build_test_plan


def run_tester_skill(*, technical_spec: dict[str, Any], implementation_plan: dict[str, Any]) -> dict[str, Any]:
    return build_test_plan(
        technical_spec=technical_spec,
        implementation_plan=implementation_plan,
        role_id="tester",
        next_role_id="reviewer",
    )
