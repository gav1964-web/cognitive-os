from __future__ import annotations

from typing import Any

from runtime._parts.config_doctor_common import _Check
from runtime._parts.config_doctor_project_feedback import check_project_development_feedback


def _check_project_development_policy(catalogs: dict[str, Any]) -> _Check:
    check = _Check("project_development_policy_integrity")
    policy = dict(catalogs["project_development_policy"])
    _check_native_failure_intake(policy, check)
    _check_diagnosis_policy(policy, check)
    _check_selection_and_options(policy, check)
    _check_outcome_execution_and_memory(policy, check)
    check_project_development_feedback(policy, check)
    _check_verified_issue_reducers(policy, catalogs, check)
    return check


def _check_native_failure_intake(policy: dict[str, Any], check: _Check) -> None:
    native_intake = dict(policy.get("native_failure_intake") or {})
    for field_name in (
        "repeat_count", "timeout_seconds", "maximum_output_chars", "pytest_arguments",
        "excluded_copy_directories", "actionable_authorities", "dependency_overlay",
    ):
        if not native_intake.get(field_name):
            check.errors.append(f"project_development_policy_missing:native_failure_intake.{field_name}")
    if int(native_intake.get("repeat_count") or 0) < 2:
        check.errors.append("project_development_policy_invalid:native_failure_intake.repeat_count")
    if native_intake.get("runner") != "pytest":
        check.errors.append("project_development_policy_invalid:native_failure_intake.runner")
    if native_intake.get("local_editable_install") is not True:
        check.errors.append("project_development_policy_invalid:native_failure_intake.local_editable_install")
    if native_intake.get("require_repeated_failure_signature") is not True:
        check.errors.append("project_development_policy_invalid:native_failure_intake.repeated_signature")
    if native_intake.get("require_unique_production_target") is not True:
        check.errors.append("project_development_policy_invalid:native_failure_intake.unique_target")
    if native_intake.get("source_apply") is not False:
        check.errors.append("project_development_policy_invalid:native_failure_intake.source_apply")


def _check_diagnosis_policy(policy: dict[str, Any], check: _Check) -> None:
    diagnosis = dict(policy.get("diagnosis_policy") or {})
    if diagnosis.get("weak_contract_zones_are_observations_only") is not True:
        check.errors.append("project_development_policy_invalid:weak_contract_observation_boundary")
    if diagnosis.get("mixed_responsibility_is_observation_only") is not True:
        check.errors.append("project_development_policy_invalid:mixed_responsibility_observation_boundary")
    if diagnosis.get("high_project_risks_are_observations_only") is not True:
        check.errors.append("project_development_policy_invalid:high_risk_observation_boundary")
    if diagnosis.get("medium_project_risks_are_observations_only") is not True:
        check.errors.append("project_development_policy_invalid:medium_risk_observation_boundary")
    if not diagnosis.get("actionable_contract_failure_authorities"):
        check.errors.append("project_development_policy_missing:actionable_contract_failure_authorities")
    elif "source_incompleteness" in diagnosis.get("actionable_contract_failure_authorities", []):
        check.errors.append("project_development_policy_invalid:uncorroborated_source_incompleteness_authority")
    if not diagnosis.get("actionable_architecture_failure_authorities"):
        check.errors.append("project_development_policy_missing:actionable_architecture_failure_authorities")
    if not diagnosis.get("actionable_medium_risk_authorities"):
        check.errors.append("project_development_policy_missing:actionable_medium_risk_authorities")
    if not diagnosis.get("actionable_high_risk_authorities"):
        check.errors.append("project_development_policy_missing:actionable_high_risk_authorities")


def _check_selection_and_options(policy: dict[str, Any], check: _Check) -> None:
    selection = dict(policy.get("selection") or {})
    if not isinstance(selection.get("minimum_confidence"), (int, float)):
        check.errors.append("project_development_policy_missing:selection.minimum_confidence")
    for field_name in ("severity_order", "route_order"):
        if not selection.get(field_name):
            check.errors.append(f"project_development_policy_missing:selection.{field_name}")
    routes = set(selection.get("route_order") or [])
    templates = dict(policy.get("option_templates") or {})
    categories = set()
    for rule_id, raw_rule in dict(policy.get("issue_rules") or {}).items():
        rule = dict(raw_rule or {})
        category = str(rule.get("category") or "")
        categories.add(category)
        for field_name in ("category", "severity", "confidence"):
            if rule.get(field_name) in (None, ""):
                check.errors.append(f"project_development_policy_missing:issue_rules.{rule_id}.{field_name}")
    for category in sorted(categories):
        options = [dict(row) for row in list(templates.get(category) or [])]
        if not options:
            check.errors.append(f"project_development_policy_missing:option_templates.{category}")
        for option in options:
            option_id = str(option.get("id") or "unknown")
            if option.get("route") not in routes:
                check.errors.append(f"project_development_policy_invalid_route:{category}.{option_id}")
            for field_name in ("value", "cost", "risk", "reversibility"):
                if not isinstance(option.get(field_name), (int, float)):
                    check.errors.append(f"project_development_policy_missing:{category}.{option_id}.{field_name}")


def _check_outcome_execution_and_memory(policy: dict[str, Any], check: _Check) -> None:
    outcome = dict(policy.get("outcome_policy") or {})
    for field_name in ("required_checks", "forbidden_success_substitutes"):
        if not outcome.get(field_name):
            check.errors.append(f"project_development_policy_missing:outcome_policy.{field_name}")
    execution = dict(policy.get("execution_policy") or {})
    for field_name in (
        "required_handoff_status", "allowed_review_recommendations",
        "maximum_verification_commands", "apply_source",
    ):
        if field_name not in execution or execution.get(field_name) in (None, ""):
            check.errors.append(f"project_development_policy_missing:execution_policy.{field_name}")
    if execution.get("apply_source") is not False:
        check.errors.append("project_development_policy_invalid:execution_policy.apply_source")
    memory = dict(policy.get("memory_policy") or {})
    if memory.get("allow_unverified_memory") is not False:
        check.errors.append("project_development_policy_invalid:memory_policy.allow_unverified_memory")
    if memory.get("allow_model_claim_as_evidence") is not False:
        check.errors.append("project_development_policy_invalid:memory_policy.allow_model_claim_as_evidence")
    if not memory.get("required_reassessment_status"):
        check.errors.append("project_development_policy_missing:memory_policy.required_reassessment_status")


def _check_verified_issue_reducers(
    policy: dict[str, Any],
    catalogs: dict[str, Any],
    check: _Check,
) -> None:
    reducers = dict(policy.get("verified_issue_reducers") or {})
    patch_recipes = dict(dict(catalogs.get("patch_synthesis_policy") or {}).get("recipes") or {})
    known_operations = {
        str(dict(recipe or {}).get("operation_kind") or "")
        for recipe in patch_recipes.values()
        if isinstance(recipe, dict)
    }
    for rule_id in dict(policy.get("issue_rules") or {}):
        if rule_id in {"weak_contracts", "mixed_responsibility", "no_safe_candidate"} and not reducers.get(rule_id):
            check.errors.append(f"project_development_policy_missing:verified_issue_reducers.{rule_id}")
        for operation_kind in list(reducers.get(rule_id) or []):
            if operation_kind not in known_operations:
                check.errors.append(
                    f"project_development_policy_unknown_reducer:{rule_id}.{operation_kind}"
                )
