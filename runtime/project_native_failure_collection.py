"""Pytest collection parsing helpers for native failure intake."""

from __future__ import annotations

from typing import Any

from .project_native_failure_binding import _normalize_nodeid

def _collected_nodeids(output: str, intake: dict[str, Any]) -> list[str]:
    nodeids = [
        _normalize_nodeid(line.strip())
        for line in output.splitlines()
        if "::" in line and not line.lstrip().startswith(("=", "<"))
    ]
    nodeids = list(dict.fromkeys(nodeids))
    maximum = max(1, int(intake.get("maximum_collected_nodeids") or 50000))
    maximum_chars = max(1, int(intake.get("maximum_collected_nodeid_chars") or 4000000))
    maximum_single = max(1, int(intake.get("maximum_collected_single_nodeid_chars") or 2048))
    if (
        len(nodeids) > maximum
        or sum(len(nodeid) for nodeid in nodeids) > maximum_chars
        or any(len(nodeid) > maximum_single for nodeid in nodeids)
    ):
        return []
    return nodeids
