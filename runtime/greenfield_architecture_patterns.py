"""Load greenfield architecture pattern records from external configuration."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PATTERNS_PATH = ROOT / "config" / "greenfield_architecture_patterns.json"


class GreenfieldArchitecturePatternError(RuntimeError):
    """Raised when greenfield architecture pattern config is invalid."""


@lru_cache(maxsize=1)
def load_greenfield_architecture_patterns(path: str | None = None) -> dict[str, Any]:
    source = Path(path) if path else PATTERNS_PATH
    payload = json.loads(source.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "greenfield_architecture_patterns.v1":
        raise GreenfieldArchitecturePatternError("greenfield patterns must use schema_version greenfield_architecture_patterns.v1")
    if payload.get("status") != "active":
        raise GreenfieldArchitecturePatternError("greenfield patterns must be active")
    defaults = payload.get("defaults")
    patterns = payload.get("patterns")
    if not isinstance(defaults, dict) or not defaults.get("pattern_id"):
        raise GreenfieldArchitecturePatternError("greenfield patterns require defaults.pattern_id")
    if not isinstance(patterns, list) or not patterns:
        raise GreenfieldArchitecturePatternError("greenfield patterns require non-empty patterns")
    _validate_pattern(defaults, require_match=False)
    seen = {str(defaults["pattern_id"])}
    for row in patterns:
        if not isinstance(row, dict):
            raise GreenfieldArchitecturePatternError("greenfield pattern rows must be objects")
        _validate_pattern({**defaults, **row}, require_match=True)
        pattern_id = str(row["pattern_id"])
        if pattern_id in seen:
            raise GreenfieldArchitecturePatternError(f"duplicate greenfield pattern_id: {pattern_id}")
        seen.add(pattern_id)
    return payload


def select_greenfield_pattern(prompt: str, *, patterns: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = patterns or load_greenfield_architecture_patterns()
    lower = prompt.lower()
    best: tuple[int, int, dict[str, Any]] | None = None
    for index, row in enumerate(payload["patterns"]):
        score = _match_score(lower, row)
        if score <= 0:
            continue
        candidate = (score, -index, row)
        if best is None or candidate > best:
            best = candidate
    selected = dict(best[2]) if best else dict(payload["defaults"])
    defaults = dict(payload["defaults"])
    merged = {**defaults, **selected}
    if selected.get("non_goals_extra"):
        merged["non_goals"] = list(defaults.get("non_goals", [])) + [str(item) for item in selected.get("non_goals_extra", [])]
    return merged


def _match_score(lower: str, row: dict[str, Any]) -> int:
    match_all = [str(item).lower() for item in row.get("match_all", [])]
    if match_all and not all(marker in lower for marker in match_all):
        return 0
    match_any = [str(item).lower() for item in row.get("match_any", [])]
    any_hits = sum(1 for marker in match_any if marker in lower)
    all_hits = len(match_all)
    return any_hits + all_hits


def _validate_pattern(row: Any, *, require_match: bool) -> None:
    if not isinstance(row, dict):
        raise GreenfieldArchitecturePatternError("greenfield pattern rows must be objects")
    required = [
        "pattern_id",
        "system_type",
        "product_summary",
        "architecture_style",
        "components",
        "main_scenarios",
        "interfaces",
        "data_model",
        "data_lifecycle",
        "external_boundaries",
        "research_hints",
        "architecture_options",
        "security_policy",
        "state_and_replay_policy",
        "risks",
        "non_goals",
        "open_questions",
        "scope",
        "primary_contract",
        "acceptance_focus",
        "constraints",
    ]
    for field in required:
        if field not in row:
            raise GreenfieldArchitecturePatternError(f"greenfield pattern {row.get('pattern_id')} requires {field}")
    if require_match and not row.get("match_any") and not row.get("match_all"):
        raise GreenfieldArchitecturePatternError(f"greenfield pattern {row.get('pattern_id')} requires match_any or match_all")
    for field in ("components", "main_scenarios", "interfaces", "data_model", "data_lifecycle", "research_hints", "architecture_options", "security_policy", "state_and_replay_policy", "risks", "non_goals", "open_questions", "scope", "acceptance_focus", "constraints"):
        if not isinstance(row.get(field), list):
            raise GreenfieldArchitecturePatternError(f"greenfield pattern {row.get('pattern_id')} field {field} must be a list")
    options = row.get("architecture_options")
    if not any(isinstance(item, dict) and item.get("status") == "chosen" for item in options):
        raise GreenfieldArchitecturePatternError(f"greenfield pattern {row.get('pattern_id')} requires a chosen architecture option")
    primary = row.get("primary_contract")
    if not isinstance(primary, dict) or not primary.get("name"):
        raise GreenfieldArchitecturePatternError(f"greenfield pattern {row.get('pattern_id')} requires primary_contract.name")
