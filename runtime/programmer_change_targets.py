"""Collect bounded source targets declared by an ImplementationPlan."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .programmer_source_location import source_location


def collect_change_targets(project_dir: Path, plan: dict[str, Any], primary: str) -> list[dict[str, Any]]:
    expected = {str(item).split(":", 1)[0] for item in list(plan.get("expected_files") or [])}
    candidates = [primary]
    candidates.extend(
        str(item.get("target") or "")
        for item in list(plan.get("change_plan") or plan.get("implementation_steps") or [])
        if isinstance(item, dict)
    )
    targets: list[dict[str, Any]] = []
    for target in dict.fromkeys(candidates):
        if not target or target.split(":", 1)[0] not in expected:
            continue
        location = source_location(project_dir, target)
        targets.append(
            {
                "target": target,
                "source_excerpt": location["excerpt"],
                "source_start_line": location["start_line"],
                "source_context": location["context"],
            }
        )
    return targets[:8]
