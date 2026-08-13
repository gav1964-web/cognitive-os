"""Admission of measured training experience into staged knowledge."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .knowledge_admission import build_kb_candidate, write_kb_candidate


def stage_training_experience(
    root: Path,
    project_dir: Path,
    diagnosis: dict[str, Any],
    before: dict[str, Any],
    after: dict[str, Any],
    outcome: dict[str, Any],
    attempts: list[dict[str, Any]],
    conclusion: dict[str, Any],
) -> Path:
    confirmed = outcome["status"] == "confirmed_improvement"
    profile = _confirmed_profile(attempts, outcome)
    if profile:
        proposed = generalized_profile_record(profile)
        proposed["training_summary"] = {
            "failure_class": diagnosis.get("failure_class"),
            "target_search_exhausted": bool(conclusion.get("target_search_exhausted")),
            "temporary_profile_score_delta": dict(conclusion.get("semantic_profile_trial") or {}).get("score_delta"),
        }
    else:
        proposed = dict(diagnosis.get("proposed_knowledge") or {})
        proposed.update({"failure_class": diagnosis.get("failure_class"), "hypothesis": diagnosis.get("hypothesis")})
        proposed["trial_conclusion"] = conclusion
    candidate = build_kb_candidate(
        record_type="semantic_contract_profile_template" if profile else "role_training_experience",
        proposed_record=proposed,
        source_cases=[{
            "project": project_dir.name,
            "status": "confirmed" if confirmed else "observed",
            "before": before["project_min_score"],
            "after": after["project_min_score"],
        }],
        teacher_reference=f"Cognitive OS self-improvement via {dict(diagnosis.get('model_trace') or {}).get('model')}",
    )
    candidate["training_outcome"] = outcome
    candidate["parameter_trials"] = [dict(row.get("parameter_changes") or {}) for row in attempts]
    return write_kb_candidate(candidate, root=root)


def generalized_profile_record(profile: dict[str, Any]) -> dict[str, Any]:
    evidence = dict(profile.get("training_evidence") or {})
    return {
        "id": str(profile.get("contract_family") or ""),
        "contract_family": profile.get("contract_family"),
        "input_contract": dict(profile.get("input_contract") or {}),
        "output_contract": dict(profile.get("output_contract") or {}),
        "side_effect_policy": dict(profile.get("side_effect_policy") or {}),
        "validation_gates": list(profile.get("validation_gates") or []),
        "failure_modes": list(profile.get("failure_modes") or []),
        "recognition_policy": {
            "source": "python_ast",
            "required_evidence": sorted(key for key, present in evidence.items() if present),
            "symbol_prefixes": ["sync_", "import_", "refresh_", "reconcile_"],
        },
        "numeric_bonus_from_training": False,
    }


def _confirmed_profile(attempts: list[dict[str, Any]], outcome: dict[str, Any]) -> dict[str, Any]:
    if outcome.get("status") != "confirmed_improvement":
        return {}
    profiles = [
        dict(dict(row.get("parameter_changes") or {}).get("temporary_semantic_profile") or {})
        for row in attempts
    ]
    return next((profile for profile in profiles if profile), {})
