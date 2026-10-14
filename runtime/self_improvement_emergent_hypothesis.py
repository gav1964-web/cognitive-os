"""Select a repeated low-scoring holdout signature for bounded redirection."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

ObservedProbe = tuple[Path, dict[str, Any] | None, dict[str, Any], bool]


def emergent_hypothesis_redirect(
    observed: list[ObservedProbe], plan: dict[str, Any], target_score: float
) -> dict[str, Any] | None:
    threshold = max(
        int(plan.get("minimum_projects") or 2),
        int(plan.get("minimum_emergent_redirect_projects") or 4),
    )
    groups: dict[str, list[ObservedProbe]] = defaultdict(list)
    for item in observed:
        _project, prepared, summary, _fresh = item
        alignment = dict(summary.get("retrieval_alignment") or {})
        signature = str(summary.get("portable_signature") or "")
        score = float(summary.get("project_min_score") or 0.0)
        if (
            prepared is not None and signature
            and not summary.get("matches_hypothesis")
            and alignment.get("aligned") and score < target_score
        ):
            groups[signature].append(item)
    candidates = sorted(groups.items(), key=lambda row: (-len(row[1]), row[0]))
    if not candidates or len(candidates[0][1]) < threshold:
        return None
    signature, items = candidates[0]
    return {
        "portable_signature": signature,
        "failure_class": signature.split("|", 1)[0],
        "observed_project_count": len(items),
        "observed_projects": sorted(item[0].name for item in items),
        "matching": [(item[0], item[1]) for item in items],
        "fresh_matching": {item[0].name.lower() for item in items if item[3]},
    }
