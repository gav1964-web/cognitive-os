"""Resolve capability requests against registered bounded improvement plugins."""

from __future__ import annotations

from typing import Any

from .self_improvement_plugin_loader import enabled_improvement_plugins


def resolve_plugin_requests(
    requests: list[dict[str, Any]], reports: list[dict[str, Any]]
) -> dict[str, Any]:
    plugins = enabled_improvement_plugins()
    providers = {
        str(capability): plugin
        for plugin in plugins
        for capability in plugin.get("implements_capabilities") or []
    }
    resolutions = []
    for request in requests:
        capability = str(request.get("missing_capability") or "")
        plugin = providers.get(capability)
        if not plugin:
            resolutions.append({
                "request_id": request.get("request_id"),
                "missing_capability": capability,
                "status": "implementation_required",
            })
            continue
        attempts = _plugin_attempts(reports, str(plugin["id"]))
        statuses = {str(row.get("status") or "") for row in attempts}
        status = (
            "trial_passed" if statuses & {"trial_passed", "promoted"}
            else "candidate_rejected" if "blocked" in statuses
            else "trial_required"
        )
        resolutions.append({
            "request_id": request.get("request_id"),
            "missing_capability": capability,
            "status": status,
            "plugin_id": plugin["id"],
            "plugin_version": plugin["version"],
            "attempt_count": len(attempts),
            "attempt_outcomes": [
                {"project": row["project"], "status": row.get("status"), "reason": row.get("reason")}
                for row in attempts
            ],
        })
    statuses = {row["status"] for row in resolutions}
    return {
        "artifact_type": "ImprovementPluginFoundryReport",
        "status": (
            "not_requested" if not resolutions
            else "trial_passed" if statuses == {"trial_passed"}
            else "candidate_rejected" if "candidate_rejected" in statuses
            else "implementation_required" if "implementation_required" in statuses
            else "trial_required"
        ),
        "request_count": len(requests),
        "resolutions": resolutions,
        "runtime_patch_auto_promotion": False,
    }


def _plugin_attempts(reports: list[dict[str, Any]], plugin_id: str) -> list[dict[str, Any]]:
    attempts: dict[str, dict[str, Any]] = {}
    for report in reports:
        project = str(report.get("project") or "")
        for cycle_name in ("improvement_plugin_cycle", "post_training_admission"):
            cycle = dict(report.get(cycle_name) or {})
            for row in list(cycle.get("attempts") or []):
                if not isinstance(row, dict) or row.get("plugin_id") != plugin_id:
                    continue
                candidate = {"project": project, **row}
                if project not in attempts or _attempt_rank(candidate) > _attempt_rank(attempts[project]):
                    attempts[project] = candidate
    return [attempts[key] for key in sorted(attempts)]


def _attempt_rank(attempt: dict[str, Any]) -> int:
    return {
        "promoted": 4, "trial_passed": 3, "blocked": 2, "not_applicable": 1,
    }.get(str(attempt.get("status") or ""), 0)
