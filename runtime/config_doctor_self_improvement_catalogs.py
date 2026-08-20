"""Load self-improvement catalogs for Config Doctor."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .promoted_candidate_selection_policies import load_selection_policies
from .promoted_executable_adapters import load_executable_adapters
from .promoted_semantic_contract_profiles import load_promoted_profiles
from .self_improvement_plugin_loader import load_improvement_plugin_catalog


def load_self_improvement_catalogs(root: Path) -> dict[str, Any]:
    return {
        "self_improvement_plugins": load_improvement_plugin_catalog(
            str(root / "config" / "self_improvement_plugins.json")
        ),
        "promoted_semantic_contract_profiles": load_promoted_profiles(
            str(root / "knowledge" / "role_knowledge" / "promoted_semantic_contract_profiles.json")
        ),
        "promoted_candidate_selection_policies": load_selection_policies(
            str(root / "knowledge" / "role_knowledge" / "promoted_candidate_selection_policies.json")
        ),
        "promoted_executable_adapters": load_executable_adapters(
            str(root / "knowledge" / "role_knowledge" / "promoted_executable_adapters.json")
        ),
    }
