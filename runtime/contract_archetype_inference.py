"""Config-driven generalized contract archetype inference."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PATH = ROOT / "config" / "contract_archetype_inference.json"


class ContractArchetypeInferenceError(RuntimeError):
    """Raised when contract archetype inference config is invalid."""


@lru_cache(maxsize=1)
def load_contract_archetypes(path: str | None = None) -> dict[str, Any]:
    source = Path(path) if path else DEFAULT_PATH
    payload = json.loads(source.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "contract_archetype_inference.v1":
        raise ContractArchetypeInferenceError("contract archetypes must use schema_version contract_archetype_inference.v1")
    archetypes = payload.get("archetypes")
    if not isinstance(archetypes, list):
        raise ContractArchetypeInferenceError("contract archetypes must contain archetypes list")
    for row in archetypes:
        if not isinstance(row, dict) or not row.get("id") or not row.get("contract_family"):
            raise ContractArchetypeInferenceError("each contract archetype requires id and contract_family")
        for field_name in (
            "symbols", "symbol_prefixes", "symbol_suffixes", "symbol_contains_any", "symbol_contains_all",
            "path_contains_any",
        ):
            if not isinstance(row.get(field_name, []), list):
                raise ContractArchetypeInferenceError(f"archetype {row.get('id')} requires {field_name} list")
    return payload


def matching_archetypes(target: str, *, path: str | None = None) -> list[dict[str, Any]]:
    payload = load_contract_archetypes(path)
    lowered = target.replace("\\", "/").lower()
    symbol = lowered.rsplit(":", 1)[-1] if ":" in lowered else lowered
    source_path = lowered.split(":", 1)[0] if ":" in lowered else ""
    matches = [row for row in payload["archetypes"] if _matches(row, source_path, symbol)]
    return sorted(matches, key=lambda row: -int(row.get("priority") or 0))


def contract_archetype_for_target(target: str) -> dict[str, Any]:
    matches = matching_archetypes(target)
    if not matches:
        return {}
    row = matches[0]
    return {
        "contract_family": row["contract_family"],
        "input_contract": dict(row.get("input_contract") or {}),
        "output_contract": dict(row.get("output_contract") or {}),
        "side_effect_policy": dict(row.get("side_effect_policy") or {}),
        "validation_gates": list(row.get("validation_gates") or []),
        "failure_modes": list(row.get("failure_modes") or []),
        "knowledge_profile": row["id"],
        "contract_archetype": row["id"],
    }


def archetype_score_adjustments(target: str) -> dict[str, Any]:
    score_delta = 0
    reasons: list[str] = []
    profile_ids: list[str] = []
    benign_runtime_boundary = False
    profiled_contract_family = False
    for row in matching_archetypes(target):
        profile_ids.append(str(row["id"]))
        score_delta += int(row.get("score_bonus") or 0)
        benign_runtime_boundary = benign_runtime_boundary or bool(row.get("benign_runtime_boundary"))
        profiled_contract_family = profiled_contract_family or bool(row.get("contract_family"))
        if row.get("reason"):
            reasons.append(str(row["reason"]))
    return {
        "score_delta": score_delta,
        "reasons": reasons,
        "profile_ids": profile_ids,
        "benign_runtime_boundary": benign_runtime_boundary,
        "profiled_contract_family": profiled_contract_family,
    }


def archetype_ranking_adjustments(target: str) -> dict[str, Any]:
    score_delta = 0
    reasons: list[str] = []
    profile_ids: list[str] = []
    for row in matching_archetypes(target):
        profile_ids.append(str(row["id"]))
        score_delta += int(row.get("ranking_bonus") or 0)
        if row.get("ranking_reason"):
            reasons.append(str(row["ranking_reason"]))
    return {"score_delta": score_delta, "reasons": reasons, "profile_ids": profile_ids}


def _matches(row: dict[str, Any], source_path: str, symbol: str) -> bool:
    if not _symbol_matches(row, symbol):
        return False
    path_tokens = [str(item).lower() for item in row.get("path_contains_any", [])]
    return not path_tokens or any(token in source_path for token in path_tokens)


def _symbol_matches(row: dict[str, Any], symbol: str) -> bool:
    exact = {str(item).lower() for item in row.get("symbols", [])}
    prefixes = tuple(str(item).lower() for item in row.get("symbol_prefixes", []))
    suffixes = tuple(str(item).lower() for item in row.get("symbol_suffixes", []))
    contains_any = [str(item).lower() for item in row.get("symbol_contains_any", [])]
    contains_all = [str(item).lower() for item in row.get("symbol_contains_all", [])]
    has_criteria = bool(exact or prefixes or suffixes or contains_any or contains_all)
    if not has_criteria:
        return True
    if exact and symbol in exact:
        return True
    if prefixes and symbol.startswith(prefixes):
        return True
    if suffixes and symbol.endswith(suffixes):
        return True
    if contains_any and any(token in symbol for token in contains_any):
        return True
    if contains_all and all(token in symbol for token in contains_all):
        return True
    return False
