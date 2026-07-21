"""Configured Stage 2 prompt-to-template routing."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from .generic_file_conversion_recipe import is_file_conversion_prompt


ROOT = Path(__file__).resolve().parents[1]
ROUTES_PATH = ROOT / "config" / "stage2_template_routes.json"


class Stage2TemplateRoutesError(RuntimeError):
    """Raised when Stage 2 template routing configuration is invalid."""


@lru_cache(maxsize=1)
def load_stage2_template_routes(path: str | None = None) -> dict[str, Any]:
    source = Path(path) if path else ROUTES_PATH
    payload = json.loads(source.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "stage2_template_routes.v1":
        raise Stage2TemplateRoutesError("stage2 template routes must use schema_version stage2_template_routes.v1")
    if payload.get("status") != "active":
        raise Stage2TemplateRoutesError("stage2 template routes must be active")
    known = payload.get("known_templates")
    routes = payload.get("routes")
    if not isinstance(known, list) or not known:
        raise Stage2TemplateRoutesError("known_templates must be a non-empty list")
    if not isinstance(routes, list) or not routes:
        raise Stage2TemplateRoutesError("routes must be a non-empty list")
    known_set = {str(item) for item in known}
    for row in routes:
        if not isinstance(row, dict) or str(row.get("case") or "") not in known_set:
            raise Stage2TemplateRoutesError("each route must reference a known template case")
    continuation = payload.get("continuation")
    if not isinstance(continuation, dict):
        raise Stage2TemplateRoutesError("continuation rules must be object")
    return payload


def known_stage2_templates(*, routes: dict[str, Any] | None = None) -> list[str]:
    payload = routes or load_stage2_template_routes()
    return [str(item) for item in payload.get("known_templates", [])]


def select_stage2_case(prompt: str, *, routes: dict[str, Any] | None = None) -> str | None:
    payload = routes or load_stage2_template_routes()
    lower = prompt.lower()
    for row in payload.get("routes", []):
        route = dict(row)
        if _route_matches(route, prompt=prompt, lower=lower):
            return str(route["case"])
    return None


def looks_like_format_continuation(prompt: str, *, routes: dict[str, Any] | None = None) -> bool:
    payload = routes or load_stage2_template_routes()
    continuation = dict(payload.get("continuation") or {})
    lower = prompt.lower()
    return _has_any(lower, continuation.get("format_change_verbs", [])) and _has_any(
        lower,
        continuation.get("format_output_markers", []),
    )


def requested_output_formats(prompt: str, *, routes: dict[str, Any] | None = None) -> list[str]:
    payload = routes or load_stage2_template_routes()
    formats = [str(item) for item in dict(payload.get("continuation") or {}).get("known_output_formats", [])]
    lower = prompt.lower()
    return [f".{item}" for item in formats if f".{item}" in lower or f" {item}" in lower]


def _route_matches(route: dict[str, Any], *, prompt: str, lower: str) -> bool:
    predicate = str(route.get("predicate") or "")
    if predicate and not _predicate_matches(predicate, prompt):
        return False
    if not _has_all(lower, route.get("all", [])):
        return False
    if route.get("any") and not _has_any(lower, route.get("any", [])):
        return False
    for group in route.get("any_groups", []) or []:
        if not _has_any(lower, group):
            return False
    optional_groups = list(route.get("any_groups_optional") or [])
    if optional_groups and not any(_has_any(lower, group) for group in optional_groups):
        return False
    return True


def _predicate_matches(predicate: str, prompt: str) -> bool:
    if predicate == "file_conversion_prompt":
        return is_file_conversion_prompt(prompt)
    return False


def _has_all(lower: str, markers: Any) -> bool:
    return all(str(marker) in lower for marker in markers or [])


def _has_any(lower: str, markers: Any) -> bool:
    return any(str(marker) in lower for marker in markers or [])
