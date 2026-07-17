"""Compatibility wrapper for TechnicalSpec artifact generation."""

from __future__ import annotations

from typing import Any

from .technical_spec_builder import build_technical_spec


def run_spec_writer_skill(*, architecture_decision: dict[str, Any]) -> dict[str, Any]:
    return build_technical_spec(
        architecture_decision=architecture_decision,
        role_id="spec_writer",
        next_role_id="implementer",
    )
