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

def _check_project_evolution_policy(catalogs: dict[str, Any]) -> _Check:
    check = _Check("project_evolution_policy_integrity")
    policy = dict(catalogs["project_evolution_policy"])
    for field_name in ("principles", "evolution_change_types", "promotion_gates", "anti_patterns"):
        if not policy.get(field_name):
            check.errors.append(f"project_evolution_policy_missing:{field_name}")
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
    return check

def _check_technical_spec_policy(catalogs: dict[str, Any]) -> _Check:
    check = _Check("technical_spec_policy_integrity")
    policy = dict(catalogs["technical_spec_policy"])
    if not policy.get("context_only_source_path_tokens"):
        check.errors.append("technical_spec_policy_missing:context_only_source_path_tokens")
    snippet = dict(policy.get("snippet_analysis") or {})
    if not snippet.get("allowed_external_names"):
        check.errors.append("technical_spec_policy_missing:snippet_analysis.allowed_external_names")
    contract = dict(policy.get("contract_type_inference") or {})
    for field_name in ("argument_rules", "payload_rules", "result_rules"):
        if not contract.get(field_name):
            check.errors.append(f"technical_spec_policy_missing:contract_type_inference.{field_name}")
    rerank = dict(policy.get("semantic_rerank") or {})
    for field_name in ("scan_limit", "strong_semantic_delta", "generic_semantic_delta"):
        if field_name not in rerank:
            check.errors.append(f"technical_spec_policy_missing:semantic_rerank.{field_name}")
    shape = dict(policy.get("architecture_shape_score") or {})
    if not shape.get("positive_source_tokens") or not shape.get("negative_source_tokens"):
        check.errors.append("technical_spec_policy_missing:architecture_shape_score.tokens")
    return check

def _check_architecture_decision_policy(catalogs: dict[str, Any]) -> _Check:
    check = _Check("architecture_decision_policy_integrity")
    policy = dict(catalogs["architecture_decision_policy"])
    fallback_archetype = dict(policy.get("fallback_archetype") or {})
    fallback_slice = dict(policy.get("fallback_slice") or {})
    source_selection = dict(policy.get("source_selection") or {})
    if not fallback_archetype.get("service_frameworks"):
        check.errors.append("architecture_decision_policy_missing:fallback_archetype.service_frameworks")
    if not fallback_slice.get("steps") or not fallback_slice.get("knowledge_rule"):
        check.errors.append("architecture_decision_policy_missing:fallback_slice.steps")
    for field_name in (
        "context_only_path_tokens",
        "domain_evidence_source_tokens",
        "provider_parser_file_globs",
        "provider_parser_function_markers",
        "fallback_read_file_path_tokens",
        "callable_transform_fallback",
        "brief_sort_rules",
    ):
        if not source_selection.get(field_name):
            check.errors.append(f"architecture_decision_policy_missing:source_selection.{field_name}")
    callable_fallback = dict(source_selection.get("callable_transform_fallback") or {})
    for field_name in ("symbol_contains_any", "path_contains_any", "excluded_symbol_prefixes", "excluded_path_tokens"):
        if not callable_fallback.get(field_name):
            check.errors.append(f"architecture_decision_policy_missing:source_selection.callable_transform_fallback.{field_name}")
    return check
