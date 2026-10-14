"""Admit structural candidate-selection lessons after independent holdout."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from runtime.improvement_plugins.candidate_selection_contrast_store import contrast_groups
from runtime.improvement_plugins.candidate_selection_holdout import (
    contrast_evidence_matches, inactive_legacy_families,
    partition_holdout_project,
)
from runtime.improvement_plugins.candidate_selection_refinement import (
    policy_signature, portable_execution_discriminators,
)
from runtime.improvement_plugins.candidate_selection_evidence import attach_ordinary_challenger_evidence
from runtime.improvement_plugins.candidate_selection_promotion import (
    promote_with_regression_gate as _promote_with_regression_gate,
)
from runtime.improvement_plugins.candidate_selection_synthesis import (
    synthesized_discriminator_families,
)
from runtime.promoted_candidate_selection_policies import (
    candidate_matches_policy,
    contrast_matches_policy,
    load_selection_policies,
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
    failure_class = str(diagnosis.get("failure_class") or "")
    groups, holdout_records = partition_holdout_project(
        _contrast_groups(root), project_dir.name, failure_class,
    )
    families = [
        *_structural_families(groups),
        *synthesized_discriminator_families(groups),
        *inactive_legacy_families(root, failure_class),
    ]
    eligible = [group for group in families if len(group["projects"]) >= minimum]
    if not families:
        if not groups:
            return {
                "status": "blocked", "reason": "confirmed_cases_required",
                "maximum_confirmed_case_count": 0,
                "minimum_confirmed_cases": minimum,
            }
        return {"status": "blocked", "reason": "no_structural_discriminator"}
    if not eligible:
        return {
            "status": "blocked", "reason": "homogeneous_confirmed_cases_required",
            "maximum_confirmed_case_count": max(len(row["projects"]) for row in families),
            "minimum_confirmed_cases": minimum,
        }
    signal = str(dict(context.get("failure_packet") or {}).get("downstream_evidence", {}).get("acceptance_signal") or "meta_only")
    effect = dict(diagnosis.get("measured_selection_effect") or {})
    if not effect:
        effect = _holdout_effect(root, project_dir, source, challenger)
    effect["treatment"] = attach_ordinary_challenger_evidence(
        effect["control"], effect["treatment"], challenger, project_dir=project_dir,
    )
    control_structural = dict(
        dict(effect.get("control", {}).get("selected_candidate_quality") or {}).get("structural_evidence") or {}
    )
    treatment_quality = dict(effect.get("treatment", {}).get("selected_candidate_quality") or {})
    treatment_structural = dict(treatment_quality.get("structural_evidence") or {})
    synthesized = [(group, group["policy"]) for group in eligible]
    applicable = [
        row for row in synthesized
        if row[1]
        and signal in set(row[1]["trigger_signals"])
        and contrast_evidence_matches(
            holdout_records, row[0]["id"], row[1], control_structural,
            treatment_structural, contrast_matches_policy,
        )
    ]
    if not applicable:
        return {"status": "blocked", "reason": "no_structural_discriminator", "failure_signal": signal}
    group, policy = applicable[0]
    if project_dir.name in group["projects"]:
        return {"status": "blocked", "reason": "independent_holdout_required", "policy_id": group["id"]}
    if _is_active(root, policy["id"]):
        return {"status": "not_applicable", "reason": "selection_policy_already_active"}
    if effect.get("status") != "confirmed_selection_effect":
        return {
            "status": "blocked", "reason": "holdout_effect_not_confirmed",
            "policy_id": policy["id"], "effect": effect,
        }
    promotion = {"applied": False, "target": "promoted_candidate_selection_policies"}
    if context.get("promote"):
        regressions = [Path(value) for value in context.get("regression_projects") or []]
        if context.get("requires_regression_cases") and not regressions:
            return {"status": "blocked", "reason": "regression_projects_required"}
        promotion = _promote_with_regression_gate(
            root, policy, group, project_dir, effect, regressions,
            int(dict(context.get("plugin_config") or {}).get("maximum_reproduction_refinements") or 1),
            int(dict(context.get("plugin_config") or {}).get("regression_verification_repetitions") or 1),
            float(dict(context.get("plugin_config") or {}).get("regression_case_timeout_seconds") or 60),
            float(dict(context.get("plugin_config") or {}).get("regression_total_timeout_seconds") or 480),
            context.get("progress"),
        )
    applied = bool(promotion.get("applied"))
    rejected = promotion.get("status") == "rejected"
    return {
        "status": "promoted" if applied else "blocked" if rejected else "trial_passed",
        **({"reason": promotion.get("reason")} if rejected else {}),
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
    return contrast_groups(root)


def _structural_families(groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    families: dict[tuple[str, str], dict[str, Any]] = {}
    for group in groups:
        for record in group["records"]:
            policy = _synthesize_policy({"id": group["id"], "records": [record]})
            if not policy:
                continue
            signature = policy_signature(policy)
            key = (str(group["id"]), signature)
            family = families.setdefault(key, {
                "id": str(group["id"]), "records": [], "projects": set(), "policy": policy,
            })
            family["records"].append(record)
            family["projects"].update(record.get("_confirmed_projects") or group["projects"])
    result = []
    for (base_id, signature), family in families.items():
        if len(family["records"]) != len(next(
            group["records"] for group in groups if group["id"] == base_id
        )):
            suffix = hashlib.sha256(signature.encode("utf-8")).hexdigest()[:10]
            family["id"] = f"{base_id}:structural_{suffix}"
            family["policy"] = {**family["policy"], "id": family["id"]}
        result.append(family)
    return sorted(result, key=lambda row: (-len(row["projects"]), row["id"]))


def _synthesize_policy(group: dict[str, Any]) -> dict[str, Any]:
    records = list(group["records"])
    failed = [dict(row.get("failed_contract") or {}) for row in records]
    successful = [dict(row.get("successful_contract") or {}) for row in records]
    requirements: dict[str, Any] = {}
    if successful and min(int(row.get("return_paths") or 0) for row in successful) > 0:
        if any(int(row.get("return_paths") or 0) == 0 for row in failed):
            requirements["min_return_paths"] = 1
            requirements["forbidden_output_inference_basis"] = ["no_value_return"]
    failed_outputs = {
        str(row.get("output_inference_basis") or "") for row in failed
        if row.get("output_inference_basis")
    }
    successful_outputs = {
        str(row.get("output_inference_basis") or "") for row in successful
        if row.get("output_inference_basis")
    }
    distinct_failed_outputs = failed_outputs - successful_outputs
    if distinct_failed_outputs and all(
        int(successful_row.get("return_paths") or 0) > 0
        and
        failed_row.get("output_inference_basis") != successful_row.get("output_inference_basis")
        for failed_row, successful_row in zip(failed, successful)
    ):
        requirements["forbidden_output_inference_basis"] = sorted(distinct_failed_outputs)
    if successful and all(not row.get("state_mutation") for row in successful) and any(row.get("state_mutation") for row in failed):
        requirements["state_mutation"] = False
    if successful and all(not row.get("literal_return_only") for row in successful) and any(
        row.get("literal_return_only") for row in failed
    ):
        requirements["literal_return_only"] = False
    if successful and all(not row.get("observed_side_effects") for row in successful):
        if any(row.get("observed_side_effects") for row in failed):
            requirements["no_observed_side_effects"] = True
    else:
        removed = [
            set(failed_row.get("observed_side_effects") or [])
            - set(successful_row.get("observed_side_effects") or [])
            for failed_row, successful_row in zip(failed, successful)
        ]
        removed = [values for values in removed if values]
        persistent = set.intersection(*removed) if removed else set()
        if persistent:
            requirements["forbidden_observed_side_effects"] = sorted(persistent)
    minimum_typed = min([int(row.get("typed_argument_count") or 0) for row in successful] or [0])
    maximum_successful_args = max([int(row.get("argument_count") or 0) for row in successful] or [0])
    minimum_failed_args = min([int(row.get("argument_count") or 0) for row in failed] or [0])
    bounded_arity = maximum_successful_args <= 1 and minimum_failed_args >= 2
    if bounded_arity:
        requirements = {"max_argument_count": 1}
    portable_requirements, portable_preflight = portable_execution_discriminators(
        failed, successful,
    )
    requirements.update(portable_requirements)
    if not requirements and minimum_typed > max(
        [int(row.get("typed_argument_count") or 0) for row in failed] or [0]
    ):
        requirements["min_typed_argument_count"] = minimum_typed
    if not requirements:
        return {}
    failed_outputs = sorted(failed_outputs)
    preflight = {}
    if requirements.get("literal_return_only") is False:
        preflight["literal_return_only"] = True
    if requirements.get("no_observed_side_effects") is True:
        preflight["observed_side_effects"] = "nonempty"
    elif requirements.get("forbidden_observed_side_effects"):
        preflight["required_observed_side_effects"] = list(
            requirements["forbidden_observed_side_effects"]
        )
    if failed_outputs and not bounded_arity:
        preflight["output_inference_basis"] = failed_outputs
    if requirements.get("max_argument_count") == 1:
        preflight["min_argument_count"] = 2
    preflight.update(portable_preflight)
    signals = sorted({str(row.get("acceptance_signal") or "meta_only") for row in failed})
    return {
        "id": str(group["id"]),
        "trigger": "executable_acceptance_rejected",
        "trigger_signals": signals,
        "structural_requirements": requirements,
        "selection_mode": "stable_partition_existing_candidates",
        "candidate_ordering": "executable_fixture_readiness",
        "preflight_trigger_requirements": preflight,
        "numeric_bonus": False,
    }


def _is_active(root: Path, policy_id: str) -> bool:
    path = root / "knowledge" / "role_knowledge" / "promoted_candidate_selection_policies.json"
    return any(
        str(row.get("id")) == policy_id
        and row.get("activation_state") in {"active", "reproduction_trial"}
        for row in load_selection_policies(str(path))["policies"]
    )


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
