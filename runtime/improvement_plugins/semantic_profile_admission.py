"""Admit repeatedly confirmed semantic contract profiles into active KB."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from runtime.knowledge_admission import load_kb_candidates
from runtime.promoted_semantic_contract_profiles import load_promoted_profiles, promote_profile
from runtime.self_improvement_contract_profile import synthesize_contract_profile
from runtime.self_improvement_experience import generalized_profile_record
from runtime.self_improvement_profile_effect import evaluate_profile_effect


PROFILE_TYPE = "semantic_contract_profile_template"
PORTABLE_FIELDS = (
    "id", "contract_family", "input_contract", "input_bindings", "output_contract",
    "side_effect_policy", "validation_gates", "failure_modes", "recognition_policy",
    "benign_runtime_boundary", "numeric_bonus_from_training",
)


def run(context: dict[str, Any]) -> dict[str, Any]:
    """Require repeated cases plus an independent same-source holdout before promotion."""
    root = Path(context["root"])
    project_dir = Path(context["project_dir"])
    source = str(dict(context.get("failure_packet") or {}).get("selected_candidate") or "")
    profile = synthesize_contract_profile(project_dir, source) if source else None
    if profile is None:
        return {"status": "not_applicable", "reason": "selected_source_has_no_supported_profile"}
    family_id = str(profile["contract_family"])
    if _is_active(root, family_id):
        return {"status": "not_applicable", "reason": "semantic_profile_already_active"}
    plugin_config = dict(context.get("plugin_config") or {})
    minimum = int(plugin_config.get("minimum_confirmed_cases") or 3)
    group = _candidate_group(root, family_id, generalized_profile_record(profile))
    projects = sorted(group.get("projects") or [])
    if len(projects) < minimum:
        return {
            "status": "blocked",
            "reason": "confirmed_cases_required",
            "profile_id": family_id,
            "confirmed_case_count": len(projects),
            "minimum_confirmed_cases": minimum,
        }
    if project_dir.name in projects:
        return {"status": "blocked", "reason": "independent_holdout_required", "profile_id": family_id}
    effect = _holdout_effect(root, project_dir, source)
    if effect.get("status") != "confirmed_profile_effect":
        return {
            "status": "blocked",
            "reason": "holdout_effect_not_confirmed",
            "profile_id": family_id,
            "effect": effect,
        }
    promotion = {"applied": False, "target": "promoted_semantic_contract_profiles"}
    if context.get("promote"):
        promoted = promote_profile(
            root=root,
            profile=dict(group["record"]),
            promotion_evidence={
                "confirmed_projects": projects,
                "holdout_project": project_dir.name,
                "holdout_score_delta": effect["score_delta"],
                "same_source_control": True,
            },
        )
        promotion = {"applied": promoted["status"] in {"promoted", "already_promoted"}, **promoted}
    applied = bool(promotion.get("applied"))
    return {
        "status": "promoted" if applied else "trial_passed",
        "change_type": "semantic_contract_profile_template",
        "profile_id": family_id,
        "promotion_applied": applied,
        "evolution": {
            "status": "passed",
            "decision": "accepted",
            "baseline": effect["control"],
            "shadow": effect["treatment"],
            "promotion": promotion,
            "gates": {
                "repeated_confirmed_cases": True,
                "independent_holdout": True,
                "same_source_effect": True,
                "no_role_regression": not effect.get("role_regressions"),
            },
        },
    }


def _candidate_group(root: Path, family_id: str, expected: dict[str, Any]) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    projects: set[str] = set()
    expected_digest = _portable_digest(expected)
    for candidate in load_kb_candidates(root=root):
        record = dict(candidate.get("proposed_record") or {})
        if candidate.get("record_type") != PROFILE_TYPE or str(record.get("id") or "") != family_id:
            continue
        if _portable_digest(record) != expected_digest:
            continue
        records.append(record)
        for case in list(candidate.get("source_cases") or []):
            row = dict(case or {})
            if row.get("status") in {"confirmed", "accepted", "verified"} and row.get("project"):
                projects.add(str(row["project"]))
    return {
        "record": _portable_record(records[0]) if records else {},
        "projects": projects,
    }


def _portable_record(record: dict[str, Any]) -> dict[str, Any]:
    return {key: record[key] for key in PORTABLE_FIELDS if key in record}


def _portable_digest(record: dict[str, Any]) -> str:
    return json.dumps(_portable_record(record), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _is_active(root: Path, family_id: str) -> bool:
    path = root / "knowledge" / "role_knowledge" / "promoted_semantic_contract_profiles.json"
    return any(str(row.get("id")) == family_id for row in load_promoted_profiles(str(path))["profiles"])


def _holdout_effect(root: Path, project_dir: Path, source: str) -> dict[str, Any]:
    from runtime.self_improvement_training import _evaluate

    return evaluate_profile_effect(
        project_dir,
        source,
        lambda: _evaluate(root, project_dir, write=True, evaluation_target=source),
    )
