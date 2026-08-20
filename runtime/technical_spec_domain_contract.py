"""Resolve static, promoted, and archetype contracts for a source candidate."""

from __future__ import annotations

from typing import Any

from .contract_archetype_inference import contract_archetype_for_target
from .promoted_semantic_contract_profiles import promoted_contract_for_candidate
from .semantic_target_profiles import contract_for_target


def domain_extraction_contract(source: str, candidate: dict[str, Any] | None = None) -> dict[str, Any]:
    profile_contract = contract_for_target(source)
    if profile_contract:
        return profile_contract
    promoted_contract = promoted_contract_for_candidate(dict(candidate or {}))
    if promoted_contract:
        return promoted_contract
    return contract_archetype_for_target(source)
