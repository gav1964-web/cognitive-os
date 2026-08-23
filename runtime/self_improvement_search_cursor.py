"""Durable search-window recovery across hypothesis plan versions."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .self_improvement_signatures import normalize_portable_signature


def prior_query_page_ends(root: Path, plan: dict[str, Any]) -> dict[str, int]:
    """Return durable page cursors for each query in one semantic hypothesis."""
    directory = root / "artifacts" / "self_improvement"
    expected = str(plan.get("portable_signature") or "")
    normalization = dict(plan.get("signature_normalization") or {})
    cursors = {str(query): 0 for query in plan.get("queries") or []}
    for path in directory.glob("hypothesis_validation_*.json"):
        try:
            report = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        prior = dict(report.get("plan") or {})
        signature = normalize_portable_signature(
            str(prior.get("portable_signature") or ""), normalization
        )
        if signature != expected:
            continue
        page_count = max(1, int(prior.get("maximum_search_pages") or 1))
        for row in report.get("discovery_rounds") or []:
            values = dict(row)
            round_number = max(1, int(values.get("round") or 1))
            start = int(values.get("search_page_start") or 0)
            if not start:
                start = 1 + (round_number - 1) * page_count
            row_queries = list(values.get("queries") or prior.get("queries") or [])
            for query in row_queries:
                key = str(query)
                if key in cursors:
                    cursors[key] = max(cursors[key], start + page_count - 1)
    return cursors


def prior_search_page_end(root: Path, plan: dict[str, Any]) -> int:
    return max(prior_query_page_ends(root, plan).values(), default=0)


def build_round_search_plan(
    plan: dict[str, Any], round_number: int, excluded: set[str]
) -> dict[str, Any]:
    cursors = dict(plan.get("query_page_cursors") or {})
    queries = list(plan.get("queries") or [])
    minimum = min((int(cursors.get(query) or 0) for query in queries), default=0)
    eligible = [query for query in queries if int(cursors.get(query) or 0) == minimum]
    limit = max(1, int(plan.get("queries_per_round") or len(eligible) or 1))
    selected = eligible[:limit]
    page_count = int(plan["maximum_search_pages"])
    hypothesis_id = str(plan["hypothesis_id"])
    return {
        **plan,
        "hypothesis_id": hypothesis_id if round_number == 1 else f"{hypothesis_id}_r{round_number}",
        "discovery_round": round_number,
        "queries": selected,
        "search_page_start": minimum + 1,
        "excluded_projects": sorted(excluded),
        "query_page_end": minimum + page_count,
    }


def advance_query_cursors(plan: dict[str, Any], round_plan: dict[str, Any]) -> None:
    cursors = dict(plan.get("query_page_cursors") or {})
    for query in round_plan.get("queries") or []:
        cursors[str(query)] = int(round_plan["query_page_end"])
    plan["query_page_cursors"] = cursors
