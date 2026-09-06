"""Token-boundary matching for project-stratum classification."""

from __future__ import annotations

import re
from typing import Any


def match_project_stratum(
    strata: list[dict[str, Any]],
    text: str,
    identity_text: str,
    authoritative_text: str,
) -> tuple[dict[str, Any], list[str]]:
    candidates = []
    fallback = None
    for index, raw in enumerate(strata):
        row = dict(raw)
        if row["id"] == "unknown_new_archetype":
            fallback = row
            continue
        search_text = identity_text if row.get("identity_only") is True else text
        matched = [
            str(marker)
            for marker in row.get("markers", [])
            if marker_matches(str(marker), search_text)
        ]
        if matched:
            identity_hits = sum(
                marker_matches(str(marker), identity_text)
                for marker in row.get("markers", [])
            )
            authoritative_hits = sum(
                marker_matches(str(marker), authoritative_text)
                for marker in row.get("markers", [])
            )
            candidates.append((
                authoritative_hits,
                identity_hits,
                len(matched),
                max(map(len, matched)),
                -index,
                row,
                matched,
            ))
    if not candidates:
        return fallback or {"id": "unknown_new_archetype", "label": "Unknown"}, []
    _, _, _, _, _, selected, matched = max(candidates, key=lambda item: item[:5])
    return selected, matched


def marker_matches(marker: str, text: str) -> bool:
    normalized = marker.lower().replace("-", "_").replace(" ", "_").strip("_")
    if not normalized:
        return False
    parts = [re.escape(part) for part in normalized.split("_") if part]
    pattern = r"(?<![a-z0-9])" + r"[_\s-]+".join(parts) + r"(?![a-z0-9])"
    return re.search(pattern, text) is not None
