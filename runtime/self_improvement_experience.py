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
    confirmed = outcome["status"] == "candidate_improvement_confirmed"
    profile = _confirmed_profile(attempts, outcome)
    selection_contrast = _selection_contrast(before, after, diagnosis, attempts, outcome)
    if profile:
        proposed = generalized_profile_record(profile)
        proposed["training_summary"] = {
            "failure_class": diagnosis.get("failure_class"),
            "target_search_exhausted": bool(conclusion.get("target_search_exhausted")),
            "temporary_profile_score_delta": dict(conclusion.get("semantic_profile_trial") or {}).get("score_delta"),
        }
    elif selection_contrast:
        proposed = selection_contrast
    else:
        proposed = dict(diagnosis.get("proposed_knowledge") or {})
        proposed.update({"failure_class": diagnosis.get("failure_class"), "hypothesis": diagnosis.get("hypothesis")})
        proposed["trial_conclusion"] = conclusion
    capability_gap = conclusion.get("recommended_change_type") == "staged_capability_gap"
    if capability_gap:
        gap_hypothesis = str(conclusion.get("next_hypothesis") or "unknown_foundation_capability")
        signature = str(conclusion.get("capability_signature") or "unclassified")
        proposed.update({
            "gap_id": f"{diagnosis.get('failure_class')}:{gap_hypothesis}:{signature}",
            "label": gap_hypothesis.replace("_", " ").capitalize(),
            "role_scope": list(diagnosis.get("target_roles") or []),
            "capability_signature": signature,
        })
    candidate = build_kb_candidate(
        record_type=(
            "semantic_contract_profile_template" if profile else
            "foundation_selection_contrast" if selection_contrast else
            "foundation_capability_gap" if capability_gap else "role_training_experience"
        ),
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


def _selection_contrast(
    before: dict[str, Any],
    after: dict[str, Any],
    diagnosis: dict[str, Any],
    attempts: list[dict[str, Any]],
    outcome: dict[str, Any],
) -> dict[str, Any]:
    if outcome.get("status") != "candidate_improvement_confirmed":
        return {}
    preferences = [
        dict(row.get("parameter_changes") or {}).get("spec_writer_candidate_preference")
        for row in attempts
    ]
    if not any(preferences):
        return {}
    failure_class = str(diagnosis.get("failure_class") or "foundation_selection")
    return {
        "contrast_id": f"{failure_class}:measured_candidate_reselection",
        "label": "Measured first-slice candidate reselection",
        "role_scope": list(diagnosis.get("target_roles") or ["architect", "spec_writer"]),
        "failed_contract": _portable_contract(before),
        "successful_contract": _portable_contract(after),
        "policy_hypothesis": "prefer candidates whose executable acceptance is independently measured",
        "activation_policy": "require independent confirmed cases before policy promotion",
        "numeric_bonus_from_training": False,
    }


def _portable_contract(case: dict[str, Any]) -> dict[str, Any]:
    quality = dict(case.get("selected_candidate_quality") or {})
    structural = dict(quality.get("structural_evidence") or {})
    downstream = dict(case.get("downstream_evidence") or {})
    return {
        "semantic_status": quality.get("status"),
        "contract_archetype_ids": list(quality.get("contract_archetype_ids") or []),
        "argument_count": structural.get("argument_count"),
        "typed_argument_count": structural.get("typed_argument_count"),
        "return_paths": structural.get("return_paths"),
        "output_inference_basis": structural.get("output_inference_basis"),
        "state_mutation": bool(structural.get("state_mutation")),
        "observed_side_effects": list(structural.get("observed_side_effects") or []),
        "acceptance_signal": downstream.get("acceptance_signal"),
        "acceptance_status": downstream.get("status"),
        "acceptance_reason": downstream.get("reason"),
    }


def generalized_profile_record(profile: dict[str, Any]) -> dict[str, Any]:
    evidence = dict(profile.get("training_evidence") or {})
    result = {
        "id": str(profile.get("contract_family") or ""),
        "contract_family": profile.get("contract_family"),
        "input_contract": dict(profile.get("input_contract") or {}),
        "output_contract": dict(profile.get("output_contract") or {}),
        "side_effect_policy": dict(profile.get("side_effect_policy") or {}),
        "validation_gates": list(profile.get("validation_gates") or []),
        "failure_modes": list(profile.get("failure_modes") or []),
        "recognition_policy": {
            "source": "python_ast",
            "recognizer": profile.get("contract_family"),
            "required_evidence": sorted(key for key, present in evidence.items() if present),
        },
        "numeric_bonus_from_training": False,
    }
    for field in ("input_bindings", "benign_runtime_boundary"):
        if profile.get(field):
            result[field] = profile[field]
    return result


def _confirmed_profile(attempts: list[dict[str, Any]], outcome: dict[str, Any]) -> dict[str, Any]:
    if outcome.get("status") != "candidate_improvement_confirmed":
        return {}
    profiles = [dict(dict(row.get("parameter_changes") or {}).get("temporary_semantic_profile") or {})
                for row in attempts if float(row.get("profile_score_delta") or 0) > 0]
    return next((profile for profile in profiles if profile), {})
