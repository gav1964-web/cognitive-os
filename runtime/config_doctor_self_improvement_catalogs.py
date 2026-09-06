"""Load self-improvement catalogs for Config Doctor."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .promoted_candidate_selection_policies import load_selection_policies
from .promoted_executable_adapters import load_executable_adapters
from .promoted_semantic_contract_profiles import load_promoted_profiles
from .self_improvement_plugin_loader import load_improvement_plugin_catalog
from .self_improvement_evidence_proposals import load_proposal_recipes
from .self_development_change import load_self_development_change_policy
from .self_development_shadow_trial import load_self_development_shadow_trial_policy
from .self_development_prospective_detection import load_prospective_detection_policy
from .self_development_l0_lifecycle import load_l0_lifecycle_policy
from .self_development_fresh_blind_trial import load_fresh_blind_trial_policy
from .self_development_corpus_eligibility import load_corpus_eligibility_policy
from .classification_consistency import load_classification_consistency_policy
from .interpreter_coverage_audit import load_interpreter_coverage_policy
from .self_development_challenge_campaign import load_challenge_campaign_policy


def load_self_improvement_catalogs(root: Path) -> dict[str, Any]:
    return {
        "self_development_change_policy": load_self_development_change_policy(
            str(root / "config" / "self_development_change_policy.json")
        ),
        "self_development_shadow_trial_policy": load_self_development_shadow_trial_policy(
            str(root / "config" / "self_development_shadow_trial.json")
        ),
        "self_development_prospective_detection_policy": load_prospective_detection_policy(
            str(root / "config" / "self_development_prospective_detection.json")
        ),
        "self_development_l0_lifecycle_policy": load_l0_lifecycle_policy(
            str(root / "config" / "self_development_l0_lifecycle.json")
        ),
        "self_development_fresh_blind_trial_policy": load_fresh_blind_trial_policy(
            str(root / "config" / "self_development_fresh_blind_trial.json")
        ),
        "self_development_corpus_eligibility_policy": load_corpus_eligibility_policy(
            str(root / "config" / "self_development_corpus_eligibility.json")
        ),
        "classification_consistency_policy": load_classification_consistency_policy(
            str(root / "config" / "classification_consistency.json")
        ),
        "interpreter_coverage_audit_policy": load_interpreter_coverage_policy(
            str(root / "config" / "interpreter_coverage_audit.json")
        ),
        "self_development_challenge_campaign_policy": load_challenge_campaign_policy(
            str(root / "config" / "self_development_challenge_campaign.json")
        ),
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
        "self_improvement_proposal_recipes": load_proposal_recipes(
            str(root / "knowledge" / "role_knowledge" / "self_improvement_proposal_recipes.json")
        ),
    }
