"""Boundary classifier for Stage 2 prompt intake."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .prompt_intake_rules import marker_groups


@dataclass(frozen=True)
class PromptBoundaryClassification:
    artifact_type: str
    status: str
    boundary: str
    confidence: float
    reasons: list[str]
    recommended_action: str
    unsupported_markers: list[str]
    risk_markers: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def classify_prompt_boundary(prompt: str, *, system_type: str | None, missing: list[str]) -> PromptBoundaryClassification:
    lower = prompt.lower()
    unsupported = _markers(lower, marker_groups("unsupported"))
    risks = _markers(lower, marker_groups("risk"))
    if "unbounded" in risks or "scope_bounded" in missing:
        return _classification("too_broad", 0.85, ["scope is unbounded"], "ask_clarification", unsupported, risks)
    if unsupported:
        return _classification("unsupported_product_surface", 0.8, ["unsupported product surface detected"], "ask_clarification", unsupported, risks)
    if system_type is None:
        return _classification("unclear_system_type", 0.7, ["bounded system type is unclear"], "ask_clarification", unsupported, risks)
    if missing:
        return _classification("incomplete_bounded_prompt", 0.7, [f"missing:{item}" for item in missing], "ask_clarification", unsupported, risks)
    if risks:
        return _classification("bounded_with_risks", 0.7, [f"risk:{item}" for item in risks], "route_to_l4_gate", unsupported, risks)
    return _classification("bounded_supported_class", 0.9, ["prompt is bounded enough for deterministic gate"], "route_to_l4_gate", unsupported, risks)


def _classification(
    boundary: str,
    confidence: float,
    reasons: list[str],
    action: str,
    unsupported: list[str],
    risks: list[str],
) -> PromptBoundaryClassification:
    return PromptBoundaryClassification(
        artifact_type="PromptBoundaryClassification",
        status="ok",
        boundary=boundary,
        confidence=confidence,
        reasons=reasons,
        recommended_action=action,
        unsupported_markers=unsupported,
        risk_markers=risks,
    )


def _markers(lower: str, groups: dict[str, list[str]]) -> list[str]:
    found: list[str] = []
    for name, markers in groups.items():
        if any(marker in lower for marker in markers):
            found.append(name)
    return found
