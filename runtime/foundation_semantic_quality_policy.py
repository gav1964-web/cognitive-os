"""Config loader for foundation semantic quality policy."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PATH = ROOT / "config" / "foundation_semantic_quality_policy.json"


class FoundationSemanticQualityPolicyError(RuntimeError):
    """Raised when foundation semantic quality policy is invalid."""


def load_foundation_semantic_quality_policy(path: str | None = None) -> dict[str, Any]:
    payload = json.loads(Path(path or DEFAULT_PATH).read_text(encoding="utf-8"))
    if payload.get("schema_version") != "foundation_semantic_quality_policy.v1":
        raise FoundationSemanticQualityPolicyError(
            "foundation semantic quality policy must use schema_version foundation_semantic_quality_policy.v1"
        )
    if not isinstance(payload.get("status_threshold"), (int, float)):
        raise FoundationSemanticQualityPolicyError("foundation semantic quality policy requires numeric status_threshold")
    for section_name in (
        "specific_text",
        "domain_profile",
        "project_analyzer",
        "architect",
        "spec_writer",
        "narrow_holdout_validation_caps",
        "source_reference",
        "side_effect_policy",
        "feedback_scoring",
    ):
        if not isinstance(payload.get(section_name), dict) or not payload.get(section_name):
            raise FoundationSemanticQualityPolicyError(f"foundation semantic quality policy missing section {section_name}")
    specific = dict(payload["specific_text"])
    if not isinstance(specific.get("min_length"), int) or not specific.get("generic_phrases"):
        raise FoundationSemanticQualityPolicyError("specific_text requires min_length and generic_phrases")
    spec_writer = dict(payload["spec_writer"])
    if not spec_writer.get("negative_case_tokens") or not spec_writer.get("weak_contract_shapes"):
        raise FoundationSemanticQualityPolicyError("spec_writer requires negative_case_tokens and weak_contract_shapes")
    source_ref = dict(payload["source_reference"])
    if not source_ref.get("tokens") and not source_ref.get("suffixes"):
        raise FoundationSemanticQualityPolicyError("source_reference requires tokens or suffixes")
    feedback = dict(payload["feedback_scoring"])
    required_feedback = {
        "unverified_handoff_caps", "meta_only_caps", "terminal_reselection_caps",
        "no_expanded_candidates_caps", "executable_confirmation_signals",
    }
    if not required_feedback <= set(feedback):
        raise FoundationSemanticQualityPolicyError("feedback_scoring is incomplete")
    validation_caps = dict(payload["narrow_holdout_validation_caps"])
    required_caps = {
        "missing_causal_diagnosis", "missing_concrete_repair_design",
        "implementation_not_ready", "change_not_validated",
    }
    if not required_caps <= set(validation_caps):
        raise FoundationSemanticQualityPolicyError("narrow_holdout_validation_caps is incomplete")
    return payload
