"""Foundation training adapter for the improvement plugin cycle."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .self_improvement_plugin_cycle import run_improvement_plugin_cycle


def run_training_improvement_plugins(
    root: Path,
    project_dir: Path,
    failure_packet: dict[str, Any],
    diagnosis: dict[str, Any],
    regression_projects: list[Path],
    *,
    promote: bool | None,
) -> tuple[dict[str, Any], dict[str, Any] | None, list[dict[str, Any]]]:
    cycle = run_improvement_plugin_cycle(
        root=root,
        project_dir=project_dir,
        failure_packet=failure_packet,
        diagnosis=diagnosis,
        regression_projects=regression_projects,
        promote=promote,
    )
    return cycle, _config_evolution_result(cycle), _training_attempts(cycle)


def run_post_training_admission(
    root: Path,
    project_dir: Path,
    failure_packet: dict[str, Any],
    diagnosis: dict[str, Any],
    regression_projects: list[Path],
    *,
    promote: bool | None,
) -> dict[str, Any]:
    """Admit a measured reselection after trials, before staging its evidence."""
    return run_improvement_plugin_cycle(
        root=root,
        project_dir=project_dir,
        failure_packet=failure_packet,
        diagnosis=diagnosis,
        regression_projects=regression_projects,
        promote=promote,
        plugin_ids={"candidate_selection_admission"},
    )


def _config_evolution_result(cycle: dict[str, Any]) -> dict[str, Any] | None:
    for attempt in list(cycle.get("attempts") or []):
        if attempt.get("plugin_id") == "config_mutation" and isinstance(attempt.get("evolution"), dict):
            return dict(attempt["evolution"])
    return None


def _training_attempts(cycle: dict[str, Any]) -> list[dict[str, Any]]:
    attempts = []
    for plugin in list(cycle.get("attempts") or []):
        evolution = dict(plugin.get("evolution") or {})
        shadow = evolution.get("shadow")
        if plugin.get("status") not in {"promoted", "trial_passed"} or not isinstance(shadow, dict):
            continue
        attempts.append({
            "parameter_changes": {"improvement_plugin": plugin.get("plugin_id")},
            "parameter_applied": plugin.get("status") == "promoted",
            "result": dict(shadow),
            "plugin_evidence": {
                "status": plugin.get("status"),
                "promotion_applied": bool(plugin.get("promotion_applied")),
            },
        })
    return attempts
