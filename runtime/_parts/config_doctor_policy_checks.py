from __future__ import annotations

from typing import Any

from runtime._parts.config_doctor_common import _Check
from runtime._parts.config_doctor_part3 import _check_structural_sample_policy


def _check_self_improvement_contract_families(catalogs: dict[str, Any]) -> _Check:
    check = _Check("self_improvement_contract_families_integrity")
    required = ("input_contract", "output_contract", "side_effect_policy", "validation_gates", "failure_modes")
    for family_id, value in dict(catalogs["self_improvement_contract_families"].get("families") or {}).items():
        family = dict(value or {})
        for field_name in required:
            if not family.get(field_name):
                check.errors.append(f"self_improvement_family_missing:{family_id}:{field_name}")
        if int(family.get("score_bonus") or 0) or int(family.get("ranking_bonus") or 0):
            check.errors.append(f"self_improvement_family_numeric_bonus_forbidden:{family_id}")
    structural = dict(catalogs["structural_contract_family_rules"])
    structural_ids = [str(dict(rule).get("family_id") or "") for rule in structural.get("rules", [])]
    if len(structural_ids) != len(set(structural_ids)):
        check.errors.append("structural_contract_family_duplicate_id")
    if not structural_ids:
        check.errors.append("structural_contract_family_rules_missing")
    templates = set(dict(catalogs["self_improvement_contract_families"].get("families") or {}))
    for family_id in sorted(set(structural_ids) - templates):
        check.errors.append(f"structural_contract_family_template_missing:{family_id}")
    return check


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
    for rule in target_quality.get("special_boundaries", []):
        value = dict(rule or {})
        if not value.get("id") or not value.get("target_contains_any") or not value.get("reason_contains_any"):
            check.errors.append("target_quality_special_boundary_invalid")
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
    _check_structural_sample_policy(policy, check)
    if not dependency.get("external_call_tokens"):
        check.errors.append("executable_acceptance_policy_missing:dependency_policy.external_call_tokens")
    stubs = dict(dependency.get("controlled_stubs") or {})
    for field_name in ("enabled", "max_missing_modules", "max_namespace_modules_per_dependency", "stub_external_missing_modules", "stub_object_features"):
        if field_name not in stubs:
            check.errors.append(f"executable_acceptance_policy_missing:dependency_policy.controlled_stubs.{field_name}")
    for field_name in ("max_missing_modules", "max_namespace_modules_per_dependency"):
        if int(stubs.get(field_name) or 0) <= 0:
            check.errors.append(f"executable_acceptance_policy_invalid:dependency_policy.controlled_stubs.{field_name}")
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
    decomposition = dict(dict(policy.get("recipes") or {}).get("extract_append_mapping_helper") or {})
    for field_name in (
        "reason",
        "operation_kind",
        "allowed_hypothesis_type",
        "required_candidate_symbol",
        "target_cluster",
        "maximum_mapping_fields",
        "required_verification",
        "differential_verification",
    ):
        if not decomposition.get(field_name):
            check.errors.append(f"patch_synthesis_policy_missing:extract_append_mapping_helper.{field_name}")
    if decomposition.get("automatic_source_mutation_allowed") is not False:
        check.errors.append(
            "patch_synthesis_policy_invalid:extract_append_mapping_helper.automatic_source_mutation_allowed"
        )
    serialization = dict(dict(policy.get("recipes") or {}).get("extract_json_dumps_helper") or {})
    for field_name in (
        "reason",
        "operation_kind",
        "allowed_hypothesis_type",
        "required_candidate_symbol",
        "target_cluster",
        "maximum_free_variables",
        "required_verification",
        "differential_verification",
    ):
        if not serialization.get(field_name):
            check.errors.append(f"patch_synthesis_policy_missing:extract_json_dumps_helper.{field_name}")
    if serialization.get("automatic_source_mutation_allowed") is not False:
        check.errors.append(
            "patch_synthesis_policy_invalid:extract_json_dumps_helper.automatic_source_mutation_allowed"
        )
    parsing = dict(dict(policy.get("recipes") or {}).get("extract_json_loads_helper") or {})
    for field_name in (
        "reason",
        "operation_kind",
        "allowed_hypothesis_type",
        "required_candidate_symbol",
        "target_cluster",
        "required_verification",
        "differential_verification",
    ):
        if not parsing.get(field_name):
            check.errors.append(f"patch_synthesis_policy_missing:extract_json_loads_helper.{field_name}")
    if parsing.get("automatic_source_mutation_allowed") is not False:
        check.errors.append(
            "patch_synthesis_policy_invalid:extract_json_loads_helper.automatic_source_mutation_allowed"
        )
    line_parsing = dict(dict(policy.get("recipes") or {}).get("extract_splitlines_helper") or {})
    for field_name in (
        "reason",
        "operation_kind",
        "allowed_hypothesis_type",
        "required_candidate_symbol",
        "target_cluster",
        "required_verification",
        "differential_verification",
    ):
        if not line_parsing.get(field_name):
            check.errors.append(f"patch_synthesis_policy_missing:extract_splitlines_helper.{field_name}")
    if line_parsing.get("automatic_source_mutation_allowed") is not False:
        check.errors.append(
            "patch_synthesis_policy_invalid:extract_splitlines_helper.automatic_source_mutation_allowed"
        )
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
