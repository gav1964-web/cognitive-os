"""Config loader for project architecture synthesis policy."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PATH = ROOT / "config" / "architecture_synthesis_policy.json"


class ArchitectureSynthesisPolicyError(RuntimeError):
    """Raised when architecture synthesis policy is invalid."""


def load_architecture_synthesis_policy(path: str | None = None) -> dict[str, Any]:
    payload = json.loads(Path(path or DEFAULT_PATH).read_text(encoding="utf-8"))
    if payload.get("schema_version") != "architecture_synthesis_policy.v1":
        raise ArchitectureSynthesisPolicyError("architecture synthesis policy must use schema_version architecture_synthesis_policy.v1")
    if payload.get("status") != "active":
        raise ArchitectureSynthesisPolicyError("architecture synthesis policy must be active")
    for section_name in (
        "fallback_target_shape",
        "default_first_slice",
        "defer",
        "verification",
        "bottlenecks",
        "task_focus",
        "confidence",
        "primary_target",
    ):
        if not payload.get(section_name):
            raise ArchitectureSynthesisPolicyError(f"architecture synthesis policy missing {section_name}")
    first_slice = dict(payload["default_first_slice"])
    if not first_slice.get("name") or not first_slice.get("goal") or not first_slice.get("steps"):
        raise ArchitectureSynthesisPolicyError("default_first_slice requires name, goal and steps")
    bottlenecks = dict(payload["bottlenecks"])
    if not bottlenecks.get("rules") or not bottlenecks.get("severity_order") or not bottlenecks.get("kind_order"):
        raise ArchitectureSynthesisPolicyError("bottlenecks requires rules, severity_order and kind_order")
    task_focus = dict(payload["task_focus"])
    if not task_focus.get("preferred_order") or "limit" not in task_focus:
        raise ArchitectureSynthesisPolicyError("task_focus requires preferred_order and limit")
    return payload
