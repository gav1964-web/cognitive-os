"""Admit structural candidate-selection lessons after independent holdout."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from runtime.knowledge_admission import load_kb_candidates
from runtime.promoted_candidate_selection_policies import (
    candidate_matches_policy,
    load_selection_policies,
    promote_selection_policy,
)


RECORD_TYPE = "foundation_selection_contrast"


def run(context: dict[str, Any]) -> dict[str, Any]:
    root = Path(context["root"])
    project_dir = Path(context["project_dir"])
    diagnosis = dict(context.get("diagnosis") or {})
    source = str(dict(context.get("failure_packet") or {}).get("selected_candidate") or "")
    challenger = str(diagnosis.get("recommended_source") or "")
    if not source or not challenger or source == challenger:
        return {"status": "not_applicable", "reason": "measured_challenger_missing"}
    minimum = int(dict(context.get("plugin_config") or {}).get("minimum_confirmed_cases") or 3)
    groups = _contrast_groups(root)
    eligible = [group for group in groups if len(group["projects"]) >= minimum]
    if not eligible:
        return {
            "status": "blocked", "reason": "confirmed_cases_required",
            "maximum_confirmed_case_count": max([len(row["projects"]) for row in groups] or [0]),
            "minimum_confirmed_cases": minimum,
        }
    signal = str(dict(context.get("failure_packet") or {}).get("downstream_evidence", {}).get("acceptance_signal") or "meta_only")
    synthesized = [
        (group, _synthesize_policy(group)) for group in eligible
    ]
    applicable = [row for row in synthesized if row[1] and signal in set(row[1]["trigger_signals"])]
    if not applicable:
        return {"status": "blocked", "reason": "no_structural_discriminator", "failure_signal": signal}
    group, policy = applicable[0]
    if project_dir.name in group["projects"]:
        return {"status": "blocked", "reason": "independent_holdout_required", "policy_id": group["id"]}
    if _is_active(root, policy["id"]):
        return {"status": "not_applicable", "reason": "selection_policy_already_active"}
    effect = _holdout_effect(root, project_dir, source, challenger)
    treatment_quality = dict(effect.get("treatment", {}).get("selected_candidate_quality") or {})
    structural = dict(treatment_quality.get("structural_evidence") or {})
    if effect.get("status") != "confirmed_selection_effect" or not candidate_matches_policy(structural, policy):
        return {
            "status": "blocked", "reason": "holdout_effect_not_confirmed",
            "policy_id": policy["id"], "effect": effect,
        }
    promotion = {"applied": False, "target": "promoted_candidate_selection_policies"}
    if context.get("promote"):
        promoted = promote_selection_policy(
            root=root,
            policy=policy,
            promotion_evidence={
                "confirmed_projects": sorted(group["projects"]),
                "holdout_project": project_dir.name,
                "holdout_score_delta": effect["score_delta"],
            },
        )
        promotion = {"applied": promoted["status"] in {"promoted", "already_promoted"}, **promoted}
    applied = bool(promotion.get("applied"))
    return {
        "status": "promoted" if applied else "trial_passed",
        "change_type": RECORD_TYPE,
        "policy_id": policy["id"],
        "promotion_applied": applied,
        "evolution": {
            "status": "passed", "decision": "accepted",
            "baseline": effect["control"], "shadow": effect["treatment"],
            "promotion": promotion,
            "gates": {
                "repeated_confirmed_cases": True,
                "independent_holdout": True,
                "structural_discriminator": True,
                "no_role_regression": not effect.get("role_regressions"),
            },
        },
    }


def _contrast_groups(root: Path) -> list[dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}
    for candidate in load_kb_candidates(root=root):
        record = dict(candidate.get("proposed_record") or {})
        if candidate.get("record_type") != RECORD_TYPE or not record.get("contrast_id"):
            continue
        group = groups.setdefault(str(record["contrast_id"]), {
            "id": str(record["contrast_id"]), "records": [], "projects": set(),
        })
        group["records"].append(record)
        for case in list(candidate.get("source_cases") or []):
            row = dict(case or {})
            if row.get("status") in {"confirmed", "accepted", "verified"} and row.get("project"):
                group["projects"].add(str(row["project"]))
    return sorted(groups.values(), key=lambda row: (-len(row["projects"]), row["id"]))


def _synthesize_policy(group: dict[str, Any]) -> dict[str, Any]:
    records = list(group["records"])
    failed = [dict(row.get("failed_contract") or {}) for row in records]
    successful = [dict(row.get("successful_contract") or {}) for row in records]
    requirements: dict[str, Any] = {}
    if successful and min(int(row.get("return_paths") or 0) for row in successful) > 0:
        if any(int(row.get("return_paths") or 0) == 0 for row in failed):
            requirements["min_return_paths"] = 1
            requirements["forbidden_output_inference_basis"] = ["no_value_return"]
    if successful and all(not row.get("state_mutation") for row in successful) and any(row.get("state_mutation") for row in failed):
        requirements["state_mutation"] = False
    minimum_typed = min([int(row.get("typed_argument_count") or 0) for row in successful] or [0])
    if minimum_typed > max([int(row.get("typed_argument_count") or 0) for row in failed] or [0]):
        requirements["min_typed_argument_count"] = minimum_typed
    if not requirements:
        return {}
    signals = sorted({str(row.get("acceptance_signal") or "meta_only") for row in failed})
    return {
        "id": str(group["id"]),
        "trigger": "executable_acceptance_rejected",
        "trigger_signals": signals,
        "structural_requirements": requirements,
        "selection_mode": "stable_partition_existing_candidates",
        "numeric_bonus": False,
    }


def _is_active(root: Path, policy_id: str) -> bool:
    path = root / "knowledge" / "role_knowledge" / "promoted_candidate_selection_policies.json"
    return any(str(row.get("id")) == policy_id for row in load_selection_policies(str(path))["policies"])


def _holdout_effect(root: Path, project_dir: Path, source: str, challenger: str) -> dict[str, Any]:
    from runtime.self_improvement_training import _evaluate

    control = _evaluate(root, project_dir, write=True, evaluation_target=source)
    treatment = _evaluate(root, project_dir, write=True, evaluation_target=challenger)
    regressions = [
        role for role, score in dict(control.get("role_scores") or {}).items()
        if score is not None and dict(treatment.get("role_scores") or {}).get(role) is not None
        and float(treatment["role_scores"][role]) < float(score)
    ]
    delta = round(float(treatment.get("project_min_score") or 0) - float(control.get("project_min_score") or 0), 2)
    executable = dict(treatment.get("downstream_evidence") or {}).get("acceptance_signal") == "executable_callable"
    selected = treatment.get("selected_extraction_candidate") == challenger
    return {
        "status": "confirmed_selection_effect" if delta > 0 and executable and selected and not regressions else "selection_effect_not_confirmed",
        "source": source, "challenger": challenger, "score_delta": delta,
        "role_regressions": regressions, "control": control, "treatment": treatment,
    }
