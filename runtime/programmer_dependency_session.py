"""Adapter between Programmer Executor strategy artifacts and dependency sessions."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .dependency_probe_session import run_dependency_probe_session


def run_executor_dependency_session(
    *, root: Path, strategy: dict[str, Any], approval: dict[str, Any] | None,
) -> dict[str, Any]:
    if not approval:
        return {}
    boundary = dict(strategy.get("dependency_boundary_profile") or {})
    profile = dict(boundary.get("isolated_environment_profile") or {})
    if not profile:
        return {
            "artifact_type": "DependencyProbeSessionResult",
            "status": "blocked",
            "reason": "profile_unavailable",
        }
    return run_dependency_probe_session(
        workspace_root=root,
        initial_profile=profile,
        session=dict(approval),
    )
