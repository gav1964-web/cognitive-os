"""Compatibility wrapper for ImplementationPlan artifact generation."""

from __future__ import annotations

from typing import Any

from .implementation_plan_builder import build_implementation_plan


def run_implementer_skill(*, technical_spec: dict[str, Any]) -> dict[str, Any]:
    return build_implementation_plan(
        technical_spec=technical_spec,
        role_id="implementer",
        next_role_id="tester",
    )
