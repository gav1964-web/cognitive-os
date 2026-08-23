"""Rank source targets by declarative architectural significance."""

from __future__ import annotations

from typing import Any

from .architecture_synthesis_policy import load_architecture_synthesis_policy


def rank_architecture_targets(
    rows: list[str], policy: dict[str, Any] | None = None
) -> list[str]:
    if policy is None:
        config = load_architecture_synthesis_policy()
        policy = dict(config.get("first_slice_target_priority") or {})
    indexed = list(enumerate(rows))
    return [
        row for _, row in sorted(
            indexed,
            key=lambda item: (-architecture_target_score(item[1], policy), item[0]),
        )
    ]


def architecture_target_score(target: str, policy: dict[str, Any] | None = None) -> int:
    if policy is None:
        config = load_architecture_synthesis_policy()
        policy = dict(config.get("first_slice_target_priority") or {})
    path, _, symbol = target.lower().replace("\\", "/").partition(":")
    score = _weighted_matches(path, policy.get("path_contains"))
    score += _weighted_matches(symbol, policy.get("symbol_contains"))
    score += _weighted_prefixes(symbol, policy.get("symbol_prefixes"))
    score -= _weighted_matches(path, policy.get("low_value_path_contains"))
    score -= _weighted_prefixes(symbol, policy.get("low_value_symbol_prefixes"))
    return score


def complete_architecture_contract(structural: dict[str, Any]) -> bool:
    annotation = str(structural.get("explicit_return_annotation") or "").strip().lower()
    has_result_path = int(structural.get("return_paths") or 0) + int(structural.get("yield_paths") or 0) > 0
    return bool(
        structural.get("source_body_complete") is True
        and int(structural.get("typed_argument_count") or 0) >= int(structural.get("argument_count") or 0)
        and annotation not in {"", "any", "typing.any", "object", "none", "nonetype"}
        and has_result_path
    )


def architecture_contract_has_priority(target: str, structural: dict[str, Any]) -> bool:
    return bool(
        architecture_target_score(target) > 0
        and complete_architecture_contract(structural)
        and structural.get("state_mutation") is not True
        and not list(structural.get("observed_side_effects") or [])
    )


def source_target_values(records: object) -> list[str]:
    targets = []
    for value in list(records or []):
        if isinstance(value, str):
            targets.append(value)
        elif isinstance(value, dict):
            target = value.get("source") or value.get("target") or value.get("capability")
            if not target and value.get("path") and value.get("name"):
                target = f"{value['path']}:{value['name']}"
            if target:
                targets.append(str(target))
    return targets


def analyzer_capability_targets(capabilities: dict[str, Any]) -> list[str]:
    return source_target_values([
        *list(capabilities.get("atomic_reusable_capabilities") or []),
        *list(capabilities.get("pure_transforms") or []),
    ])


def _weighted_matches(value: str, records: object) -> int:
    return sum(
        int(row.get("weight") or 0)
        for row in list(records or [])
        if isinstance(row, dict) and str(row.get("token") or "").lower() in value
    )


def _weighted_prefixes(value: str, records: object) -> int:
    return sum(
        int(row.get("weight") or 0)
        for row in list(records or [])
        if isinstance(row, dict) and value.startswith(str(row.get("token") or "").lower())
    )
