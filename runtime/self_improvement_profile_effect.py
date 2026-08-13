"""Measure and stage the attributable effect of one temporary profile."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from .knowledge_admission import build_kb_candidate, write_kb_candidate
from .self_improvement_contract_profile import synthesize_contract_profile
from .self_improvement_experience import generalized_profile_record
from .semantic_target_profiles import temporary_semantic_profiles


def evaluate_profile_effect(
    project_dir: Path,
    source: str,
    evaluate: Callable[[], dict[str, Any]],
) -> dict[str, Any]:
    profile = synthesize_contract_profile(project_dir, source)
    if profile is None:
        return {"status": "not_recognized", "source": source}
    control = evaluate()
    with temporary_semantic_profiles([profile]):
        treatment = evaluate()
    delta = round(treatment["project_min_score"] - control["project_min_score"], 2)
    regressions = [
        role for role, score in dict(control.get("role_scores") or {}).items()
        if score is not None and dict(treatment.get("role_scores") or {}).get(role) is not None
        and treatment["role_scores"][role] < score
    ]
    return {
        "status": "confirmed_profile_effect" if delta > 0 and not regressions else "profile_effect_not_confirmed",
        "source": source,
        "contract_family": profile["contract_family"],
        "profile": profile,
        "control": control,
        "treatment": treatment,
        "score_delta": delta,
        "role_regressions": regressions,
    }


def stage_profile_effect(root: Path, project_dir: Path, effect: dict[str, Any]) -> Path | None:
    if effect.get("status") != "confirmed_profile_effect":
        return None
    proposed = generalized_profile_record(dict(effect["profile"]))
    proposed["effect_evidence"] = {
        "control_score": effect["control"]["project_min_score"],
        "treatment_score": effect["treatment"]["project_min_score"],
        "score_delta": effect["score_delta"],
        "same_source_control": True,
    }
    candidate = build_kb_candidate(
        record_type="semantic_contract_profile_template",
        proposed_record=proposed,
        source_cases=[{
            "project": project_dir.name,
            "status": "confirmed",
            "before": effect["control"]["project_min_score"],
            "after": effect["treatment"]["project_min_score"],
        }],
        teacher_reference="Cognitive OS same-source profile effect trial",
    )
    candidate["profile_effect"] = {key: effect[key] for key in ("source", "contract_family", "score_delta")}
    return write_kb_candidate(candidate, root=root)
