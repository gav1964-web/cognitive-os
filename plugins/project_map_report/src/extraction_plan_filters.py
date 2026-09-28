"""Filters for runtime extraction plan candidates."""

from __future__ import annotations

from typing import Any

from .extraction_ranking import is_whole_workflow_wrapper_name


def suppress_whole_workflow_wrappers(plan: list[dict[str, Any]]) -> list[dict[str, Any]]:
    narrow = [item for item in plan if not is_whole_workflow_wrapper_name(_capability_symbol(str(item.get("capability") or "")))]
    if len(narrow) >= 3:
        return narrow
    return plan


def _capability_symbol(capability: str) -> str:
    return capability.rsplit(":", 1)[-1].lower()
