from __future__ import annotations

from pathlib import Path
from typing import Any

from runtime._parts.config_doctor_common import _Check
from runtime.role_workflow_contracts import workflow_dataflow_errors
from runtime.role_workflow_handler_registry import workflow_handler_registration_errors


def _check_pilot_profile(catalogs: dict[str, Any]) -> _Check:
    check = _Check("pilot_profile_integrity")
    profile = dict(catalogs["pilot_profile"])
    strata = {str(row.get("id")) for row in catalogs["role_project_type_policy"].get("strata", [])}
    unknown_strata = set(profile.get("allowed_project_strata") or []) - strata
    if unknown_strata:
        check.errors.append(f"pilot_profile_unknown_strata:{sorted(unknown_strata)}")
    if not profile.get("allowed_modes") or not profile.get("allowed_effect_modes"):
        check.errors.append("pilot_profile_missing_allowed_modes")
    if dict(profile.get("source_apply") or {}).get("allowed") is not False:
        check.errors.append("pilot_profile_source_apply_must_be_disabled")
    transfer = dict(profile.get("transfer_gate") or {})
    if int(transfer.get("minimum_blind_projects") or 0) < 2:
        check.errors.append("pilot_profile_blind_project_floor_too_low")
    if int(transfer.get("minimum_independent_lineages") or 0) < 2:
        check.errors.append("pilot_profile_lineage_floor_too_low")
    if not profile.get("required_roles"):
        check.errors.append("pilot_profile_missing_required_roles")
    telemetry = dict(profile.get("telemetry_gate") or {})
    if int(telemetry.get("minimum_reviewed_runs") or 0) < 2:
        check.errors.append("pilot_profile_telemetry_run_floor_too_low")
    rate = float(telemetry.get("minimum_first_pass_rate") or 0.0)
    if not 0.0 < rate <= 1.0:
        check.errors.append("pilot_profile_invalid_first_pass_rate")
    if int(telemetry.get("maximum_handoff_loss") or 0) != 0:
        check.errors.append("pilot_profile_handoff_loss_must_be_zero")
    if int(telemetry.get("maximum_pending_reviews") or 0) != 0:
        check.errors.append("pilot_profile_pending_reviews_must_be_zero")
    return check


def _check_pilot_blind_corpus_policy(catalogs: dict[str, Any]) -> _Check:
    check = _Check("pilot_blind_corpus_policy_integrity")
    policy = dict(catalogs["pilot_blind_corpus_policy"])
    if policy.get("schema_version") != "github_blind_corpus_strata.v1":
        check.errors.append("pilot_blind_corpus_policy_invalid_schema")
    if int(policy.get("projects_per_stratum") or 0) < 1:
        check.errors.append("pilot_blind_corpus_policy_empty_strata")
    if policy.get("unique_owners") is not True:
        check.errors.append("pilot_blind_corpus_policy_requires_unique_owners")
    strata = list(policy.get("strata") or [])
    if len(strata) < 2:
        check.errors.append("pilot_blind_corpus_policy_requires_two_strata")
    if any(not row.get("id") or not row.get("queries") for row in strata):
        check.errors.append("pilot_blind_corpus_policy_invalid_stratum")
    return check


def _check_programmer_task_tree_policy(catalogs: dict[str, Any]) -> _Check:
    check = _Check("programmer_task_tree_policy_integrity")
    policy = dict(catalogs["programmer_task_tree_policy"])
    limits = dict(policy.get("limits") or {})
    if policy.get("status") != "active":
        check.errors.append("programmer_task_tree_policy_not_active")
    for field_name in ("expected_files", "changes", "acceptance", "max_nodes"):
        if int(limits.get(field_name) or 0) <= 0:
            check.errors.append(f"programmer_task_tree_policy_invalid_limit:{field_name}")
    for field_name in ("required_gates", "allowed_actions", "forbidden_actions", "stop_conditions"):
        if not policy.get(field_name):
            check.errors.append(f"programmer_task_tree_policy_missing:{field_name}")
    expected_max = int(limits.get("changes") or 0) + int(limits.get("acceptance") or 0) + 3
    if int(limits.get("max_nodes") or 0) < expected_max:
        check.errors.append("programmer_task_tree_policy_max_nodes_too_small")
    return check


def _check_role_directory(catalogs: dict[str, Any]) -> _Check:
    check = _Check("role_directory_pipeline_integrity")
    directory = catalogs["role_directory"]
    roles = dict(directory.get("roles") or {})
    outputs: set[str] = set()
    stages = list(dict(directory.get("workflow") or {}).get("stages") or [])
    check.errors.extend(workflow_handler_registration_errors(stages))
    initial_state = list(dict(directory.get("workflow") or {}).get("initial_state") or [])
    check.errors.extend(workflow_dataflow_errors(stages, initial_state))
    for step in directory.get("pipeline", []):
        role_id = str(dict(step).get("role_id") or "")
        role = dict(roles.get(role_id) or {})
        if role_id not in roles:
            check.errors.append(f"unknown_pipeline_role:{role_id}")
            continue
        output_key = str(dict(step).get("output_key") or "")
        if output_key in outputs:
            check.errors.append(f"duplicate_pipeline_output_key:{output_key}")
        outputs.add(output_key)
        builder = dict(role.get("artifact_builder") or {})
        if not builder.get("callable") or not builder.get("artifact_type"):
            check.errors.append(f"missing_builder_contract:{role_id}")
    return check


def _check_stage2_routes(catalogs: dict[str, Any], root: Path) -> _Check:
    check = _Check("stage2_template_routes_integrity")
    routes = catalogs["stage2_template_routes"]
    known = {str(item) for item in routes.get("known_templates", [])}
    routed = {str(dict(row).get("case") or "") for row in routes.get("routes", [])}
    for case_name in sorted(routed - known):
        check.errors.append(f"route_unknown_case:{case_name}")
    for case_name in sorted(known - routed):
        check.warnings.append(f"known_template_without_route:{case_name}")
    curriculum = root / "curricula" / "programmer_prompt_stage2"
    for case_name in sorted(known):
        if not (curriculum / case_name / "teacher_reference.json").is_file():
            check.warnings.append(f"template_without_teacher_reference:{case_name}")
    return check


def _check_semantic_resolution(catalogs: dict[str, Any]) -> _Check:
    check = _Check("semantic_resolution_references")
    known = {str(item) for item in catalogs["stage2_template_routes"].get("known_templates", [])}
    rules = catalogs["semantic_resolution_rules"]
    for row in rules.get("existing_resolution_rules", []):
        required = str(dict(row).get("required_template") or "")
        if required not in known:
            check.errors.append(f"semantic_rule_unknown_template:{required}")
    return check


def _check_semantic_target_profiles(catalogs: dict[str, Any]) -> _Check:
    check = _Check("semantic_target_profiles_integrity")
    seen = set()
    for row in catalogs["semantic_target_profiles"].get("profiles", []):
        profile = dict(row)
        profile_id = str(profile.get("id") or "")
        if profile_id in seen:
            check.errors.append(f"duplicate_semantic_target_profile:{profile_id}")
        seen.add(profile_id)
        symbol_fields = ("symbols", "symbol_prefixes", "symbol_contains_any", "symbol_contains_all")
        if not any(profile.get(field_name) for field_name in symbol_fields):
            check.errors.append(f"semantic_target_profile_without_symbol_matcher:{profile_id}")
        for excluded in profile.get("exclude_if_profile_ids", []):
            if str(excluded) not in seen and not any(
                str(candidate.get("id") or "") == str(excluded)
                for candidate in catalogs["semantic_target_profiles"].get("profiles", [])
            ):
                check.errors.append(f"semantic_target_profile_unknown_exclusion:{profile_id}:{excluded}")
        if profile.get("contract_family"):
            required = ["input_contract", "output_contract", "side_effect_policy", "validation_gates", "failure_modes"]
            for field_name in required:
                ok = isinstance(profile.get(field_name), dict) if field_name == "input_contract" else bool(profile.get(field_name))
                if not ok:
                    check.errors.append(f"semantic_target_contract_missing_{field_name}:{profile_id}")
        if profile.get("score_bonus") and profile.get("score_penalty"):
            check.warnings.append(f"semantic_target_profile_has_bonus_and_penalty:{profile_id}")
    return check


def _check_web_extraction_profiles(catalogs: dict[str, Any]) -> _Check:
    check = _Check("web_extraction_profiles_integrity")
    seen = set()
    for row in catalogs["web_extraction_profiles"].get("profiles", []):
        host = str(dict(row).get("host") or "")
        kind = str(dict(row).get("target_kind") or "")
        key = (host, kind)
        if key in seen:
            check.errors.append(f"duplicate_web_extraction_profile:{kind}:{host}")
        seen.add(key)
        if not host or "." not in host:
            check.errors.append(f"invalid_web_extraction_host:{host}")
        if kind not in {"news"}:
            check.warnings.append(f"unknown_web_extraction_target_kind:{kind}:{host}")
    return check


def _check_operation_recipes(catalogs: dict[str, Any]) -> _Check:
    check = _Check("operation_recipe_references")
    rules = catalogs["operation_recipe_rules"]
    contracts = set(catalogs["interface_contracts"])
    profiles = set(dict(catalogs["sandbox_programmer_profiles"].get("profiles") or {}))
    for contract in rules.get("allowed_interface_contracts", []):
        if str(contract) not in contracts:
            check.errors.append(f"unknown_interface_contract:{contract}")
    for contract, profile in dict(rules.get("contract_profiles") or {}).items():
        if str(contract) not in contracts:
            check.errors.append(f"contract_profile_unknown_contract:{contract}")
        if str(profile) not in profiles:
            check.errors.append(f"contract_profile_unknown_profile:{profile}")
    for row in rules.get("text_interface_resolution", []):
        contract = str(dict(row).get("interface_contract") or "")
        if contract not in contracts:
            check.errors.append(f"text_resolution_unknown_contract:{contract}")
    return check


def _check_sandbox_programmer(catalogs: dict[str, Any]) -> _Check:
    check = _Check("sandbox_programmer_registry_integrity")
    profiles = set(dict(catalogs["sandbox_programmer_profiles"].get("profiles") or {}))
    operations = {str(row.get("id") or ""): dict(row) for row in catalogs["sandbox_operations"].get("operations", [])}
    for operation_id, row in sorted(operations.items()):
        profile = str(row.get("profile") or "")
        if profile not in profiles:
            check.errors.append(f"operation_unknown_profile:{operation_id}:{profile}")
    seen = set()
    for operation_id in operations:
        if operation_id in seen:
            check.errors.append(f"duplicate_operation_id:{operation_id}")
        seen.add(operation_id)
    for composition in catalogs["sandbox_compositions"].get("compositions", []):
        for step in dict(composition).get("steps", []):
            operation_id = str(dict(step).get("operation") or "")
            if operation_id not in operations:
                check.errors.append(f"composition_unknown_operation:{dict(composition).get('id')}:{operation_id}")
    return check


def _check_sandbox_attempt_policy(catalogs: dict[str, Any], root: Path) -> _Check:
    check = _Check("sandbox_attempt_policy_references")
    policy = catalogs["sandbox_attempt_policy"]
    known = {str(item) for item in catalogs["stage2_template_routes"].get("known_templates", [])}
    curriculum = root / "curricula" / "programmer_prompt_stage2"
    for kind, entry in dict(policy.get("allowed_attempt_kinds") or {}).items():
        for case_name in dict(entry).get("cases", []):
            case = str(case_name)
            if case not in known:
                check.errors.append(f"attempt_kind_unknown_case:{kind}:{case}")
            if dict(entry).get("requires_curriculum_reference") and not (curriculum / case / "teacher_reference.json").is_file():
                check.errors.append(f"attempt_kind_missing_teacher_reference:{kind}:{case}")
    return check


def _check_l4_decision_rules(catalogs: dict[str, Any]) -> _Check:
    check = _Check("l4_decision_rule_integrity")
    seen = set()
    for rule in catalogs["l4_decision_rules"].get("rules", []):
        rule_id = str(dict(rule).get("rule_id") or "")
        if rule_id in seen:
            check.errors.append(f"duplicate_l4_rule_id:{rule_id}")
        seen.add(rule_id)
        if not dict(rule).get("next_action"):
            check.errors.append(f"l4_rule_without_next_action:{rule_id}")
    return check


def _check_architecture_synthesis_policy(catalogs: dict[str, Any]) -> _Check:
    check = _Check("architecture_synthesis_policy_integrity")
    policy = dict(catalogs["architecture_synthesis_policy"])
    if policy.get("status") != "active":
        check.errors.append("architecture_synthesis_policy_inactive")
    if not policy.get("fallback_target_shape"):
        check.errors.append("architecture_synthesis_policy_missing:fallback_target_shape")
    first_slice = dict(policy.get("default_first_slice") or {})
    for field_name in ("name", "goal", "target_task_types", "steps"):
        if not first_slice.get(field_name):
            check.errors.append(f"architecture_synthesis_policy_missing:default_first_slice.{field_name}")
    bottlenecks = dict(policy.get("bottlenecks") or {})
    if not bottlenecks.get("rules"):
        check.errors.append("architecture_synthesis_policy_missing:bottlenecks.rules")
    for row in list(bottlenecks.get("rules") or []):
        rule = dict(row)
        for field_name in ("kind", "source", "reason", "severity"):
            if not rule.get(field_name):
                check.errors.append(f"architecture_synthesis_bottleneck_rule_missing:{field_name}")
    if not dict(policy.get("task_focus") or {}).get("preferred_order"):
        check.errors.append("architecture_synthesis_policy_missing:task_focus.preferred_order")
    return check


def _check_foundation_semantic_quality_policy(catalogs: dict[str, Any]) -> _Check:
    check = _Check("foundation_semantic_quality_policy_integrity")
    policy = dict(catalogs["foundation_semantic_quality_policy"])
    if not isinstance(policy.get("status_threshold"), (int, float)):
        check.errors.append("foundation_semantic_quality_policy_missing:status_threshold")
    for section_name in (
        "specific_text",
        "domain_profile",
        "project_analyzer",
        "architect",
        "spec_writer",
        "source_reference",
        "side_effect_policy", "feedback_scoring",
    ):
        if not isinstance(policy.get(section_name), dict) or not policy.get(section_name):
            check.errors.append(f"foundation_semantic_quality_policy_missing:{section_name}")
    if not dict(policy.get("specific_text") or {}).get("generic_phrases"):
        check.errors.append("foundation_semantic_quality_policy_missing:specific_text.generic_phrases")
    if not dict(policy.get("spec_writer") or {}).get("negative_case_tokens"):
        check.errors.append("foundation_semantic_quality_policy_missing:spec_writer.negative_case_tokens")
    executable_floor = dict(policy.get("spec_writer") or {}).get(
        "executable_confirmation_floor_score"
    )
    if not isinstance(executable_floor, (int, float)) or not 9.7 <= float(executable_floor) <= 9.8:
        check.errors.append(
            "foundation_semantic_quality_policy_invalid:"
            "spec_writer.executable_confirmation_floor_score"
        )
    return check


def _check_role_project_type_policy(catalogs: dict[str, Any]) -> _Check:
    check = _Check("role_project_type_policy_integrity")
    policy = dict(catalogs["role_project_type_policy"])
    if not policy.get("roles") or not policy.get("strata"):
        check.errors.append("role_project_type_policy_missing:roles_or_strata")
    if not dict(policy.get("evidence_thresholds") or {}):
        check.errors.append("role_project_type_policy_missing:evidence_thresholds")
    demonstration = dict(policy.get("demonstration_thresholds") or {})
    if int(demonstration.get("minimum_project_native_transformations") or 0) < 1:
        check.errors.append("role_project_type_policy_requires_native_transformations")
    unknown = next(
        (dict(row) for row in policy.get("strata", []) if row.get("id") == "unknown_new_archetype"),
        {},
    )
    if unknown.get("maturity_allowed") is not False:
        check.errors.append("role_project_type_policy_unknown_must_not_mature")
    lifecycle = dict(policy.get("unknown_archetype_lifecycle") or {})
    if int(lifecycle.get("minimum_confirmed_projects") or 0) < 2:
        check.errors.append("role_project_type_policy_unknown_requires_repeated_projects")
    confidence = lifecycle.get("minimum_evidence_confidence")
    if not isinstance(confidence, (int, float)) or not 0 < float(confidence) <= 1:
        check.errors.append("role_project_type_policy_unknown_invalid_confidence")
    chain = dict(policy.get("role_chain_evaluation") or {})
    if not 0 < float(chain.get("minimum_interaction_score") or 0) <= 1:
        check.errors.append("role_project_type_policy_invalid_chain_score")
    if not chain.get("required_known_roles") or "researcher" not in chain.get("conditional_roles", []):
        check.errors.append("role_project_type_policy_incomplete_chain_roles")
    priority = dict(policy.get("development_priority") or {})
    current = dict(priority.get("current_lane") or {})
    deferred = dict(priority.get("deferred_lane") or {})
    current_strata = set(current.get("project_strata") or [])
    deferred_strata = set(deferred.get("project_strata") or [])
    scored_strata = {
        str(row.get("id") or "")
        for row in policy.get("strata") or []
        if row.get("identity_only") is not True and row.get("maturity_allowed") is not False
    }
    if current_strata != {"cli_local_tool", "library_pure_transform"}:
        check.errors.append("role_project_type_policy_invalid_narrow_current_lane")
    if current_strata & deferred_strata or current_strata | deferred_strata != scored_strata:
        check.errors.append("role_project_type_policy_development_lanes_do_not_partition_strata")
    if float(current.get("target_score") or 0.0) < 9.7:
        check.errors.append("role_project_type_policy_narrow_target_below_9_7")
    if float(deferred.get("target_score") or 0.0) < 9.7 or deferred.get("required_later") is not True:
        check.errors.append("role_project_type_policy_broad_lane_not_required_later")
    return check
