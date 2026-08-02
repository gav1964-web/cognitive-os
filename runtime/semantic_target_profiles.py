"""Config-driven semantic target profiles and contract families."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PATH = ROOT / "config" / "semantic_target_profiles.json"


class SemanticTargetProfileError(RuntimeError):
    """Raised when semantic target profiles are invalid."""


@lru_cache(maxsize=1)
def load_semantic_target_profiles(path: str | None = None) -> dict[str, Any]:
    source = Path(path) if path else DEFAULT_PATH
    payload = json.loads(source.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "semantic_target_profiles.v1":
        raise SemanticTargetProfileError("semantic target profiles must use schema_version semantic_target_profiles.v1")
    profiles = payload.get("profiles")
    if not isinstance(profiles, list):
        raise SemanticTargetProfileError("semantic target profiles must contain profiles list")
    for row in profiles:
        if not isinstance(row, dict) or not row.get("id"):
            raise SemanticTargetProfileError("each semantic target profile requires id")
        for field_name in ("symbols", "symbol_prefixes", "symbol_contains_any", "symbol_contains_all", "path_contains_any"):
            if not isinstance(row.get(field_name, []), list):
                raise SemanticTargetProfileError(f"profile {row.get('id')} requires {field_name} list when present")
    return payload


def matching_profiles(target: str, *, path: str | None = None) -> list[dict[str, Any]]:
    payload = load_semantic_target_profiles(path)
    lowered = target.replace("\\", "/").lower()
    symbol = lowered.rsplit(":", 1)[-1] if ":" in lowered else lowered
    source_path = lowered.split(":", 1)[0] if ":" in lowered else ""
    matched = [profile for profile in payload["profiles"] if _matches(profile, source_path, symbol)]
    matched_ids = {str(profile.get("id")) for profile in matched}
    return [
        profile
        for profile in matched
        if not (set(str(item) for item in profile.get("exclude_if_profile_ids", [])) & matched_ids)
    ]


def contract_for_target(target: str) -> dict[str, Any]:
    for profile in matching_profiles(target):
        if profile.get("contract_family"):
            return {
                "contract_family": profile["contract_family"],
                "input_contract": dict(profile.get("input_contract") or {}),
                "output_contract": dict(profile.get("output_contract") or {}),
                "side_effect_policy": dict(profile.get("side_effect_policy") or {}),
                "validation_gates": list(profile.get("validation_gates") or []),
                "failure_modes": list(profile.get("failure_modes") or []),
                "knowledge_profile": profile["id"],
            }
    return {}


def semantic_score_adjustments(target: str) -> dict[str, Any]:
    score_delta = 0
    reasons: list[str] = []
    penalty_reasons: list[str] = []
    profile_ids: list[str] = []
    benign_runtime_boundary = False
    profiled_contract_family = False
    for profile in matching_profiles(target):
        profile_ids.append(str(profile["id"]))
        score_delta += int(profile.get("score_bonus") or 0)
        score_delta -= int(profile.get("score_penalty") or 0)
        benign_runtime_boundary = benign_runtime_boundary or bool(profile.get("benign_runtime_boundary"))
        profiled_contract_family = profiled_contract_family or bool(profile.get("contract_family"))
        if profile.get("reason"):
            reasons.append(str(profile["reason"]))
        if profile.get("penalty_reason"):
            penalty_reasons.append(str(profile["penalty_reason"]))
    return {
        "score_delta": score_delta,
        "reasons": reasons,
        "penalty_reasons": penalty_reasons,
        "profile_ids": profile_ids,
        "benign_runtime_boundary": benign_runtime_boundary,
        "profiled_contract_family": profiled_contract_family,
    }


def semantic_ranking_adjustments(target: str) -> dict[str, Any]:
    score_delta = 0
    reasons: list[str] = []
    profile_ids: list[str] = []
    for profile in matching_profiles(target):
        profile_ids.append(str(profile["id"]))
        score_delta += int(profile.get("ranking_bonus") or 0)
        score_delta -= int(profile.get("ranking_penalty") or 0)
        if profile.get("ranking_reason"):
            reasons.append(str(profile["ranking_reason"]))
    return {
        "score_delta": score_delta,
        "reasons": reasons,
        "profile_ids": profile_ids,
    }


def has_profile(target: str, profile_id: str) -> bool:
    return any(str(profile.get("id")) == profile_id for profile in matching_profiles(target))


def _matches(profile: dict[str, Any], source_path: str, symbol: str) -> bool:
    if not _symbol_matches(profile, symbol):
        return False
    path_tokens = [str(item).lower() for item in profile.get("path_contains_any", [])]
    return not path_tokens or any(token in source_path for token in path_tokens)


def _symbol_matches(profile: dict[str, Any], symbol: str) -> bool:
    exact = {str(item).lower() for item in profile.get("symbols", [])}
    prefixes = tuple(str(item).lower() for item in profile.get("symbol_prefixes", []))
    contains_any = [str(item).lower() for item in profile.get("symbol_contains_any", [])]
    contains_all = [str(item).lower() for item in profile.get("symbol_contains_all", [])]
    has_criteria = bool(exact or prefixes or contains_any or contains_all)
    if not has_criteria:
        return True
    if exact and symbol in exact:
        return True
    if prefixes and symbol.startswith(prefixes):
        return True
    if contains_any and any(token in symbol for token in contains_any):
        return True
    if contains_all and all(token in symbol for token in contains_all):
        return True
    return False
