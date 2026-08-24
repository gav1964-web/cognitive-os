"""Execute the bounded detect-trial-verify-promote plugin cycle."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .self_improvement_plugin_loader import (
    enabled_improvement_plugins,
    load_improvement_entrypoint,
    load_improvement_plugin_catalog,
)


def run_improvement_plugin_cycle(
    *,
    root: Path,
    project_dir: Path,
    failure_packet: dict[str, Any],
    diagnosis: dict[str, Any],
    regression_projects: list[Path],
    promote: bool | None = None,
    plugin_ids: set[str] | None = None,
) -> dict[str, Any]:
    """Run applicable plugins and stop after the first proven promotion."""
    catalog = load_improvement_plugin_catalog()
    cycle_policy = dict(catalog.get("cycle") or {})
    limit = int(cycle_policy.get("max_plugins_per_failure") or 1)
    attempts: list[dict[str, Any]] = []
    plugins = [
        plugin for plugin in enabled_improvement_plugins()
        if plugin_ids is None or str(plugin["id"]) in plugin_ids
    ]
    for plugin in plugins[:limit]:
        handler = load_improvement_entrypoint(str(plugin["entrypoint"]))
        promotion_requested = bool(plugin.get("auto_promote")) if promote is None else bool(promote)
        result = handler({
            "root": root,
            "project_dir": project_dir,
            "failure_packet": failure_packet,
            "diagnosis": diagnosis,
            "regression_projects": regression_projects,
            "promote": promotion_requested,
            "requires_regression_cases": bool(plugin.get("requires_regression_cases")),
            "plugin_config": plugin,
        })
        attempt = {
            "plugin_id": plugin["id"],
            "plugin_version": plugin["version"],
            "promotion_requested": promotion_requested,
            **dict(result or {}),
        }
        attempts.append(attempt)
        diagnosis = _chain_trial_result(diagnosis, failure_packet, attempt)
        if attempt.get("status") == "promoted" and cycle_policy.get("stop_after_promotion", True):
            break
    return {
        "artifact_type": "SelfImprovementPluginCycleReport",
        "status": _cycle_status(attempts),
        "attempts": attempts,
        "promotion_count": sum(row.get("status") == "promoted" for row in attempts),
        "applicable_plugin_count": sum(row.get("status") != "not_applicable" for row in attempts),
    }


def _cycle_status(attempts: list[dict[str, Any]]) -> str:
    if any(row.get("status") == "promoted" for row in attempts):
        return "promoted"
    if any(row.get("status") == "trial_passed" for row in attempts):
        return "trial_passed"
    if any(row.get("status") == "blocked" for row in attempts):
        return "blocked"
    return "not_applicable"


def _chain_trial_result(
    diagnosis: dict[str, Any], packet: dict[str, Any], attempt: dict[str, Any]
) -> dict[str, Any]:
    challenger = str(attempt.get("selected_challenger") or "")
    evolution = dict(attempt.get("evolution") or {})
    control, shadow = dict(evolution.get("baseline") or {}), dict(evolution.get("shadow") or {})
    if attempt.get("status") != "trial_passed" or not challenger or not shadow:
        return diagnosis
    return {**diagnosis,
        "recommended_source": challenger,
        "measured_selection_effect": {
            "status": "confirmed_selection_effect",
            "source": packet.get("selected_candidate"),
            "challenger": challenger,
            "score_delta": round(
                float(shadow.get("project_min_score") or 0)
                - float(control.get("project_min_score") or 0), 2,
            ),
            "role_regressions": [], "control": control, "treatment": shadow,
        },
    }
