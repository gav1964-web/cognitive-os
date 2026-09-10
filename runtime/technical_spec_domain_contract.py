"""Resolve static, promoted, and archetype contracts for a source candidate."""

from __future__ import annotations

from typing import Any

from .contract_archetype_inference import contract_archetype_for_target
from .promoted_semantic_contract_profiles import promoted_contract_for_candidate
from .semantic_target_profiles import contract_for_target
from .source_contract_semantics import infer_source_contract
from .target_structural_families import structural_contract_for_candidate


def domain_extraction_contract(source: str, candidate: dict[str, Any] | None = None) -> dict[str, Any]:
    profile_contract = contract_for_target(source)
    if profile_contract:
        return profile_contract
    promoted_contract = promoted_contract_for_candidate(dict(candidate or {}))
    if promoted_contract:
        return promoted_contract
    archetype_contract = contract_archetype_for_target(source)
    if archetype_contract:
        return archetype_contract
    return structural_contract_for_candidate(infer_source_contract(dict(candidate or {})))
