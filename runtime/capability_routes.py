"""Config-driven route matching from goals to capability sets."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RULES_PATH = ROOT / "config" / "capability_routes.json"


class CapabilityRoutesError(RuntimeError):
    """Raised when capability route rules are invalid."""


@lru_cache(maxsize=1)
def load_capability_routes(path: str | None = None) -> dict[str, Any]:
    source = Path(path) if path else RULES_PATH
    payload = json.loads(source.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "capability_routes.v1":
        raise CapabilityRoutesError("capability routes must use schema_version capability_routes.v1")
    if payload.get("status") != "active":
        raise CapabilityRoutesError("capability routes must be active")
    routes = payload.get("routes")
    if not isinstance(routes, list):
        raise CapabilityRoutesError("capability routes require routes list")
    for row in routes:
        if not isinstance(row, dict) or not row.get("route_id"):
            raise CapabilityRoutesError("capability route requires route_id")
        if not isinstance(row.get("all_groups"), list) or not isinstance(row.get("capabilities"), list):
            raise CapabilityRoutesError("capability route requires all_groups and capabilities lists")
    return payload


def match_capability_route(goal: str, *, rules: dict[str, Any] | None = None) -> list[str]:
    row = match_capability_route_row(goal, rules=rules)
    if row is None:
        return []
    return [str(item) for item in row.get("capabilities") or []]


def match_capability_route_row(goal: str, *, rules: dict[str, Any] | None = None) -> dict[str, Any] | None:
    payload = rules or load_capability_routes()
    lowered = " ".join(goal.lower().split())
    for row in sorted(payload.get("routes") or [], key=lambda item: int(dict(item).get("priority") or 100)):
        if _matches_all_groups(lowered, row.get("all_groups") or []):
            return dict(row)
    return None


def missing_capability_hint(goal: str, *, rules: dict[str, Any] | None = None) -> str | None:
    payload = rules or load_capability_routes()
    lowered = " ".join(goal.lower().split())
    for row in payload.get("missing_capability_hints") or []:
        markers = [str(item) for item in dict(row).get("markers") or []]
        if any(marker in lowered for marker in markers):
            return str(dict(row).get("hint") or "")
    return None


def _matches_all_groups(lowered: str, groups: list[Any]) -> bool:
    for group in groups:
        markers = [str(item).lower() for item in group]
        if not any(marker in lowered for marker in markers):
            return False
    return True
