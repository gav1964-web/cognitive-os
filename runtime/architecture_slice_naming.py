"""Semantic first-slice names derived from configured target profiles."""

from __future__ import annotations

from .foundation_semantic_quality_policy import load_foundation_semantic_quality_policy
from .semantic_target_profiles import matching_profiles


def semantic_first_slice_name(current_name: str, targets: list[str]) -> str:
    name = str(current_name or "first_bounded_capability_slice")
    if _is_specific_name(name):
        return name
    for target in targets:
        for profile in matching_profiles(str(target)):
            if profile.get("contract_family") and profile.get("id"):
                return _profile_slice_name(str(profile["id"]))
    return name


def _is_specific_name(name: str) -> bool:
    architect = dict(load_foundation_semantic_quality_policy().get("architect") or {})
    generic = {str(item).lower() for item in architect.get("generic_first_slice_names", [])}
    generic.add("first_bounded_capability_slice")
    return name.lower() not in generic


def _profile_slice_name(profile_id: str) -> str:
    stem = profile_id.removesuffix("_boundary").removesuffix("_transform")
    return f"{stem}_slice"
