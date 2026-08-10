from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable
from runtime.architecture_decision_policy import load_architecture_decision_policy
from runtime.architecture_synthesis_policy import load_architecture_synthesis_policy
from runtime.foundation_semantic_quality_policy import load_foundation_semantic_quality_policy
from runtime.interface_contracts import load_interface_contracts
from runtime.greenfield_architecture_patterns import load_greenfield_architecture_patterns
from runtime.l4_decision_table import load_l4_decision_rules
from runtime.operation_recipe_rules import load_operation_recipe_rules
from runtime.prompt_intake_rules import load_prompt_intake_rules
from runtime.role_directory import load_role_directory
from runtime.runtime_interpreter_policy import load_runtime_interpreter_policy
from runtime.sandbox_programmer_profiles import load_sandbox_programmer_profiles
from runtime.sandbox_release_policy import load_sandbox_release_policy
from runtime.semantic_target_profiles import load_semantic_target_profiles
from runtime.semantic_resolution_rules import load_semantic_resolution_rules
from runtime.stage2_template_routes import load_stage2_template_routes
from runtime.target_quality_policy import load_target_quality_policy
from runtime.technical_spec_policy import load_technical_spec_policy
from runtime.web_extraction_profiles import load_web_extraction_profiles

ROOT = Path(__file__).resolve().parents[2]

def _check_target_quality_policy(catalogs: dict[str, Any]) -> _Check:
    check = _Check("target_quality_policy_integrity")
    policy = dict(catalogs["target_quality_policy"])
    target_quality = dict(policy.get("target_quality") or {})
    ranking = dict(policy.get("spec_writer_ranking") or {})
    for field_name in (
        "suspicious_path_tokens",
        "suspicious_symbol_tokens",
        "representative_tokens",
        "strong_contract_tokens",
        "runtime_boundary_tokens",
        "trivial_symbols",
    ):
        if not target_quality.get(field_name):
            check.errors.append(f"target_quality_policy_missing:{field_name}")
    for section_name in (
        "repair_loop",
        "operational_boundary",
        "domain_contract",
        "representative_slice",
        "trivial_helper",
        "bootstrap_support",
        "low_value_first_slice",
        "mutation_like_first_slice",
    ):
        if not isinstance(ranking.get(section_name), dict) or not ranking.get(section_name):
            check.errors.append(f"spec_writer_policy_missing_section:{section_name}")
    if not ranking.get("deterministic_shape_tokens"):
        check.errors.append("spec_writer_policy_missing:deterministic_shape_tokens")
    return check

def _check_executable_acceptance_policy(catalogs: dict[str, Any]) -> _Check:
    check = _Check("executable_acceptance_policy_integrity")
    policy = dict(catalogs["executable_acceptance_policy"])
    dependency = dict(policy.get("dependency_policy") or {})
    samples = dict(policy.get("sample_values") or {})
    if not dependency.get("external_call_tokens"):
        check.errors.append("executable_acceptance_policy_missing:dependency_policy.external_call_tokens")
    stubs = dict(dependency.get("controlled_stubs") or {})
    for field_name in ("enabled", "max_missing_modules", "stub_external_missing_modules", "stub_object_features"):
        if field_name not in stubs:
            check.errors.append(f"executable_acceptance_policy_missing:dependency_policy.controlled_stubs.{field_name}")
    if int(stubs.get("max_missing_modules") or 0) <= 0:
        check.errors.append("executable_acceptance_policy_invalid:dependency_policy.controlled_stubs.max_missing_modules")
    for feature in ("getitem", "mro_entries"):
        if feature not in stubs.get("stub_object_features", []):
            check.errors.append(f"executable_acceptance_policy_missing:dependency_policy.controlled_stubs.stub_object_features.{feature}")
    metadata = dict(dependency.get("metadata_profiles") or {})
    for field_name in ("enabled", "default_version", "packages"):
        if not metadata.get(field_name):
            check.errors.append(f"executable_acceptance_policy_missing:dependency_policy.metadata_profiles.{field_name}")
    for package_name in ("cookiecutter", "invoke", "isort", "paramiko", "pre_commit"):
        if package_name not in metadata.get("packages", []):
            check.errors.append(f"executable_acceptance_policy_missing:dependency_policy.metadata_profiles.packages.{package_name}")
    generated = dict(dependency.get("generated_module_profiles") or {})
    if not generated.get("enabled") or not generated.get("modules"):
        check.errors.append("executable_acceptance_policy_missing:dependency_policy.generated_module_profiles")
    for module_name in ("borg._version", "urllib3._version", "filelock.version", "tox.version", "virtualenv.version"):
        if module_name not in dict(generated.get("modules") or {}):
            check.errors.append(f"executable_acceptance_policy_missing:dependency_policy.generated_module_profiles.modules.{module_name}")
    method_policy = dict(policy.get("method_fixture_policy") or {})
    for field_name in ("enabled", "safe_uninitialized_instance", "default_constructor_first", "recipes"):
        if field_name not in method_policy:
            check.errors.append(f"executable_acceptance_policy_missing:method_fixture_policy.{field_name}")
    recovery = dict(policy.get("skipped_recovery") or {})
    for reason in ("import_failed_missing_module", "positive_sample_execution_failed", "method_target_needs_instance_fixture"):
        if not recovery.get(reason):
            check.errors.append(f"executable_acceptance_policy_missing:skipped_recovery.{reason}")
    for field_name in ("field_values", "type_contains", "signature_type_contains", "fixture_fields"):
        if not samples.get(field_name):
            check.errors.append(f"executable_acceptance_policy_missing:sample_values.{field_name}")
    field_values = dict(samples.get("field_values") or {})
    for field_name in ("annotation", "value", "param_name", "is_path_param"):
        if field_name not in field_values:
            check.errors.append(f"executable_acceptance_policy_missing:sample_values.field_values.{field_name}")
    if dict(samples.get("type_contains") or {}).get("bool") is not True:
        check.errors.append("executable_acceptance_policy_invalid:type_contains.bool")
    if dict(samples.get("signature_type_contains") or {}).get("bool") is not False:
        check.errors.append("executable_acceptance_policy_invalid:signature_type_contains.bool")
    return check

def _check_patch_synthesis_policy(catalogs: dict[str, Any]) -> _Check:
    check = _Check("patch_synthesis_policy_integrity")
    policy = dict(catalogs["patch_synthesis_policy"])
    literal = dict(dict(policy.get("recipes") or {}).get("return_literal_stub") or {})
    for field_name in ("reason", "operation_kind", "positive_case_kind", "expect_keys", "max_literal_repr_chars"):
        if not literal.get(field_name):
            check.errors.append(f"patch_synthesis_policy_missing:return_literal_stub.{field_name}")
    notimplemented = dict(dict(policy.get("recipes") or {}).get("return_literal_notimplemented") or {})
    for field_name in ("reason", "operation_kind", "positive_case_kind", "expect_keys", "max_literal_repr_chars"):
        if not notimplemented.get(field_name):
            check.errors.append(f"patch_synthesis_policy_missing:return_literal_notimplemented.{field_name}")
    transform = dict(dict(policy.get("recipes") or {}).get("contract_transform_identity_return") or {})
    for field_name in ("reason", "operation_kind", "positive_case_kind", "expect_keys", "allowed_transforms"):
        if not transform.get(field_name):
            check.errors.append(f"patch_synthesis_policy_missing:contract_transform_identity_return.{field_name}")
    operator_ids = {str(row.get("id") or "") for row in list(dict(catalogs.get("contract_transform_operators") or {}).get("operators") or [])}
    for operator_id in list(transform.get("allowed_transforms") or []):
        if str(operator_id) not in operator_ids:
            check.errors.append(f"patch_synthesis_policy_unknown_transform:{operator_id}")
    recipe = dict(dict(policy.get("recipes") or {}).get("required_input_guard") or {})
    if not recipe:
        check.errors.append("patch_synthesis_policy_missing:recipes.required_input_guard")
        return check
    for field_name in (
        "reason",
        "operation_kind",
        "max_required_inputs",
        "missing_input_case",
        "positive_case_kind",
        "ignored_signature_parameters",
        "already_present_markers",
        "named_argument_guard",
        "kwargs_guard",
    ):
        if not recipe.get(field_name):
            check.errors.append(f"patch_synthesis_policy_missing:required_input_guard.{field_name}")
    if "self" not in recipe.get("ignored_signature_parameters", []):
        check.errors.append("patch_synthesis_policy_invalid:required_input_guard.ignored_signature_parameters")
    if int(recipe.get("max_required_inputs") or 0) <= 0:
        check.errors.append("patch_synthesis_policy_invalid:required_input_guard.max_required_inputs")
    return check


def _check_contract_transform_operators(catalogs: dict[str, Any]) -> _Check:
    check = _Check("contract_transform_operators_integrity")
    catalog = dict(catalogs["contract_transform_operators"])
    admission = dict(catalog.get("admission_policy") or {})
    if admission.get("automatic_source_mutation_allowed") is not False:
        check.errors.append("contract_transform_operators_invalid:automatic_source_mutation_allowed")
    seen = set()
    for row in [dict(item) for item in list(catalog.get("operators") or [])]:
        operator_id = str(row.get("id") or "")
        if not operator_id:
            check.errors.append("contract_transform_operators_missing:id")
        if operator_id in seen:
            check.errors.append(f"contract_transform_operators_duplicate:{operator_id}")
        seen.add(operator_id)
        for field_name in ("input_kind", "output_kind", "expression_template"):
            if not row.get(field_name):
                check.errors.append(f"contract_transform_operators_missing:{field_name}:{operator_id}")
        if "{arg}" not in str(row.get("expression_template") or ""):
            check.errors.append(f"contract_transform_operators_invalid_template:{operator_id}")
    return check


def _check_contract_transform_contract_profiles(catalogs: dict[str, Any]) -> _Check:
    check = _Check("contract_transform_contract_profiles_integrity")
    catalog = dict(catalogs["contract_transform_contract_profiles"])
    admission = dict(catalog.get("admission_policy") or {})
    if admission.get("automatic_acceptance_mutation_allowed") is not False:
        check.errors.append("contract_transform_profiles_invalid:automatic_acceptance_mutation_allowed")
    operator_ids = {str(row.get("id") or "") for row in list(dict(catalogs["contract_transform_operators"]).get("operators") or [])}
    seen = set()
    for row in [dict(item) for item in list(catalog.get("profiles") or [])]:
        profile_id = str(row.get("id") or "")
        if not profile_id:
            check.errors.append("contract_transform_profiles_missing:id")
        if profile_id in seen:
            check.errors.append(f"contract_transform_profiles_duplicate:{profile_id}")
        seen.add(profile_id)
        if str(row.get("operator_id") or "") not in operator_ids:
            check.errors.append(f"contract_transform_profiles_unknown_operator:{profile_id}")
        for field_name in ("name_tokens", "input_field_candidates", "input_types", "output_types", "expect_key"):
            if not row.get(field_name):
                check.errors.append(f"contract_transform_profiles_missing:{field_name}:{profile_id}")
        if "sample_input" not in row or "expected_output" not in row:
            check.errors.append(f"contract_transform_profiles_missing:sample_or_expected:{profile_id}")
    return check


def _check_programmer_executor_playbooks(catalogs: dict[str, Any]) -> _Check:
    check = _Check("programmer_executor_playbooks_integrity")
    policy = dict(catalogs["programmer_executor_playbooks"])
    admission = dict(policy.get("admission_policy") or {})
    if admission.get("automatic_source_mutation_allowed") is not False:
        check.errors.append("executor_playbooks_invalid:automatic_source_mutation_allowed")
    playbooks = [dict(row) for row in list(policy.get("playbooks") or [])]
    if not playbooks:
        check.errors.append("executor_playbooks_missing:playbooks")
    seen = set()
    for row in playbooks:
        playbook_id = str(row.get("id") or "")
        if not playbook_id:
            check.errors.append("executor_playbooks_missing:id")
        if playbook_id in seen:
            check.errors.append(f"executor_playbooks_duplicate:{playbook_id}")
        seen.add(playbook_id)
        if not dict(row.get("match") or {}):
            check.errors.append(f"executor_playbooks_missing:match:{playbook_id}")
        if not row.get("action") or not row.get("safe_next_step"):
            check.errors.append(f"executor_playbooks_missing:action_or_next_step:{playbook_id}")
        if not row.get("required_gates"):
            check.errors.append(f"executor_playbooks_missing:required_gates:{playbook_id}")
    return check


def _check_executor_solution_patterns(catalogs: dict[str, Any]) -> _Check:
    check = _Check("executor_solution_patterns_integrity")
    catalog = dict(catalogs["executor_solution_patterns"])
    admission = dict(catalog.get("admission_policy") or {})
    if admission.get("automatic_source_mutation_allowed") is not False:
        check.errors.append("executor_solution_patterns_invalid:automatic_source_mutation_allowed")
    patterns = [dict(row) for row in list(catalog.get("patterns") or [])]
    if not patterns:
        check.errors.append("executor_solution_patterns_missing:patterns")
    seen = set()
    for row in patterns:
        pattern_id = str(row.get("id") or "")
        if pattern_id in seen:
            check.errors.append(f"executor_solution_patterns_duplicate:{pattern_id}")
        seen.add(pattern_id)
        for field_name in ("match", "action", "safe_next_step", "required_evidence", "risk"):
            if not row.get(field_name):
                check.errors.append(f"executor_solution_patterns_missing:{field_name}:{pattern_id}")
    return check


def _check_project_evolution_policy(catalogs: dict[str, Any]) -> _Check:
    check = _Check("project_evolution_policy_integrity")
    policy = dict(catalogs["project_evolution_policy"])
    for field_name in (
        "principles",
        "chosen_path",
        "development_lanes",
        "decision_rules",
        "stop_signals",
        "evidence_milestones",
        "evolution_rules",
        "evolution_change_types",
        "promotion_gates",
        "anti_patterns",
    ):
        if not policy.get(field_name):
            check.errors.append(f"project_evolution_policy_missing:{field_name}")
    chosen = dict(policy.get("chosen_path") or {})
    for field_name in ("north_star", "architecture_bet", "field_trial_role", "promotion_rule", "implementation_rule"):
        if not chosen.get(field_name):
            check.errors.append(f"project_evolution_policy_missing:chosen_path.{field_name}")
    lanes = dict(policy.get("development_lanes") or {})
    for lane_name in ("evidence_calibration", "role_contract_depth", "kb_generalization", "negative_controls"):
        lane = dict(lanes.get(lane_name) or {})
        if not lane.get("goal") or not lane.get("primary_artifacts"):
            check.errors.append(f"project_evolution_policy_missing:development_lanes.{lane_name}")
    decisions = dict(policy.get("decision_rules") or {})
    for rule_name in ("add_kb_when", "change_role_logic_when", "split_or_promote_role_when", "declare_separate_track_when"):
        if not decisions.get(rule_name):
            check.errors.append(f"project_evolution_policy_missing:decision_rules.{rule_name}")
    milestones = dict(policy.get("evidence_milestones") or {})
    for milestone_name, minimum in (("calibrated_9_5", 160), ("calibrated_9_7", 320)):
        milestone = dict(milestones.get(milestone_name) or {})
        if int(milestone.get("minimum_scored_projects") or 0) < minimum:
            check.errors.append(f"project_evolution_policy_invalid:evidence_milestones.{milestone_name}")
    gates = dict(policy.get("promotion_gates") or {})
    for gate_name in ("role_score_9_5", "role_score_9_7"):
        gate = dict(gates.get(gate_name) or {})
        if not gate.get("required_evidence"):
            check.errors.append(f"project_evolution_policy_missing:promotion_gates.{gate_name}.required_evidence")
        if int(gate.get("minimum_field_callable_delta") or 0) <= 0:
            check.errors.append(f"project_evolution_policy_invalid:promotion_gates.{gate_name}.minimum_field_callable_delta")
    changes = dict(policy.get("evolution_change_types") or {})
    if "kb_crystallization" not in changes or "field_validated_capability" not in changes:
        check.errors.append("project_evolution_policy_missing:core_change_types")
    rules = dict(policy.get("evolution_rules") or {})
    for rule_name in (
        "score_growth_requires_independent_holdout",
        "previous_field_cannot_validate_new_level",
        "false_callable_is_regression",
        "meta_only_is_not_callable",
        "native_extension_boundary_is_separate_track",
        "line_limit_blocks_promotion",
    ):
        if not dict(rules.get(rule_name) or {}).get("blocker"):
            check.errors.append(f"project_evolution_policy_missing:evolution_rules.{rule_name}.blocker")
    return check

def _check_role_promotion_policy(catalogs: dict[str, Any]) -> _Check:
    check = _Check("role_promotion_policy_integrity")
    policy = dict(catalogs["role_promotion_policy"])
    bands = dict(policy.get("score_bands") or {})
    roles = dict(policy.get("first_four_roles") or {})
    band_97 = dict(bands.get("9_7") or {})
    for item in ("independent_holdout", "unseen_project_types", "line_limit_check", "no_source_changes"):
        if item not in set(band_97.get("required_evidence") or []):
            check.errors.append(f"role_promotion_policy_missing:9_7.required_evidence.{item}")
    for role_id in ("project_analyzer", "architect", "spec_writer", "implementer"):
        role = dict(roles.get(role_id) or {})
        if float(role.get("target_score") or 0.0) < 9.7:
            check.errors.append(f"role_promotion_policy_invalid:{role_id}.target_score")
        for field_name in ("required_checks", "required_semantic_checks", "growth_focus"):
            if not role.get(field_name):
                check.errors.append(f"role_promotion_policy_missing:{role_id}.{field_name}")
    return check

def _check_llm_profiles(catalogs: dict[str, Any]) -> _Check:
    check = _Check("llm_profiles_integrity")
    profiles = dict(dict(catalogs["llm_profiles"]).get("profiles") or {})
    for profile_id in ("local_l35", "external_l45_intent_resolver"):
        profile = dict(profiles.get(profile_id) or {})
        if not profile:
            check.errors.append(f"llm_profile_missing:{profile_id}")
            continue
        for field_name in ("base_url", "model", "provider_label", "timeout_seconds", "response_format"):
            if field_name not in profile:
                check.errors.append(f"llm_profile_missing:{profile_id}.{field_name}")
        if not str(profile.get("base_url") or "").rstrip("/").endswith("/v1"):
            check.warnings.append(f"llm_profile_base_url_not_openai_v1:{profile_id}")
        if float(profile.get("timeout_seconds") or 0) <= 0:
            check.errors.append(f"llm_profile_invalid_timeout:{profile_id}")
        if not isinstance(profile.get("response_format"), bool):
            check.errors.append(f"llm_profile_invalid_response_format:{profile_id}")
    return check

def _check_role_source_policy(catalogs: dict[str, Any]) -> _Check:
    check = _Check("role_source_policy_integrity")
    policy = dict(catalogs["role_source_policy"])
    section = dict(policy.get("implementation_target_policy") or {})
    for field_name in ("context_only_path_tokens", "context_only_file_tokens", "blocked_by"):
        if not section.get(field_name):
            check.errors.append(f"role_source_policy_missing:{field_name}")
    required_path_tokens = {"/tests/", "/integration_tests/", "/docs/", "/examples/", "/tools/"}
    actual_path_tokens = {str(item) for item in list(section.get("context_only_path_tokens") or [])}
    for token in sorted(required_path_tokens - actual_path_tokens):
        check.errors.append(f"role_source_policy_missing_context_token:{token}")
    if "context_only_implementation_target" not in section.get("blocked_by", []):
        check.errors.append("role_source_policy_missing_blocker:context_only_implementation_target")
    scope = dict(policy.get("scope_selection_policy") or {})
    for field_name in (
        "candidate_excluded_dirs",
        "candidate_noise_parts",
        "candidate_noise_suffixes",
        "disfavored_roots",
        "manifest_names",
        "preferred_roots",
        "syntax_fixture_roots",
    ):
        if not scope.get(field_name):
            check.errors.append(f"role_source_policy_missing_scope_field:{field_name}")
    required_scope_roots = {"src", "lib"}
    actual_scope_roots = {str(item) for item in list(scope.get("preferred_roots") or [])}
    for token in sorted(required_scope_roots - actual_scope_roots):
        check.errors.append(f"role_source_policy_missing_preferred_scope_root:{token}")
    return check
