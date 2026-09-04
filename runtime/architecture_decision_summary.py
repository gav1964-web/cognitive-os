from __future__ import annotations

from typing import Any


def decision_summary(summary: dict[str, Any], capabilities: list[dict[str, Any]], risks: list[dict[str, Any]]) -> str:
    project = summary.get("root", "project")
    return f"Treat {project} as a candidate for bounded capability extraction: {len(capabilities)} capability candidates, {len(risks)} architecture risks."


def source_strata(readiness: dict[str, Any]) -> dict[str, Any]:
    strata = readiness.get("source_strata", {})
    if not isinstance(strata, dict):
        return {}
    return {
        "active_core": list(strata.get("active_core", []))[:24],
        "legacy_noise": list(strata.get("legacy_noise", []))[:24],
        "context_only": list(strata.get("context_only", []))[:24],
        "packaged_copy": list(strata.get("packaged_copy", []))[:24],
        "policy": "Use active_core for first extraction candidates; keep legacy_noise/context_only as evidence, not first targets.",
    }
