from __future__ import annotations

from typing import Any

from runtime._parts.config_doctor_part1 import _Check


def _check_structural_sample_policy(policy: dict[str, Any], check: _Check) -> None:
    structural = dict(policy.get("structural_sample_policy") or {})
    fields = (
        "priorities", "conversion_samples", "numeric_sequence_calls", "attribute_samples",
        "length_constraint_samples",
        "unpack_samples",
        "protocol_method_prefixes",
        "format_samples", "format_pattern", "module_attribute_calls", "collection_difference_method",
    )
    for field_name in fields:
        if not structural.get(field_name):
            check.errors.append(f"executable_acceptance_policy_missing:structural_sample_policy.{field_name}")
    required = {
        "allowed_collection_domain", "comparison_literal", "conversion", "importable_module_path",
        "keyword_payload", "length_constraint", "numeric_arithmetic", "numeric_sequence",
        "parameter_attributes", "parameter_unpack", "required_mapping_keys", "split_unpack",
        "strptime_format", "validation_format_hint",
    }
    priorities = dict(structural.get("priorities") or {})
    for name in sorted(required - priorities.keys()):
        check.errors.append(f"executable_acceptance_policy_missing:structural_sample_policy.priorities.{name}")


def _check_executable_acceptance_source_isolation(catalogs: dict[str, Any]) -> _Check:
    check = _Check("executable_acceptance_source_isolation_integrity")
    policy = dict(catalogs["executable_acceptance_policy"])
    foundation = dict(policy.get("foundation_evidence") or {})
    if not foundation.get("isolated_transitive_effects"):
        check.errors.append("executable_acceptance_policy_missing:foundation_evidence.isolated_transitive_effects")
    direct_profiles = dict(foundation.get("isolated_direct_effect_profiles") or {})
    if not direct_profiles or any(not name or not effects for name, effects in direct_profiles.items()):
        check.errors.append("executable_acceptance_policy_invalid:foundation_evidence.isolated_direct_effect_profiles")
    isolation = dict(policy.get("source_isolation_policy") or {})
    profiles = dict(isolation.get("effect_module_stubs") or {})
    if not profiles:
        check.errors.append("executable_acceptance_source_isolation_missing:effect_module_stubs")
    for module_name, profile in profiles.items():
        attrs = dict(dict(profile or {}).get("attributes") or {})
        if not module_name or not attrs:
            check.errors.append(f"executable_acceptance_source_isolation_invalid:{module_name}")
        for value in attrs.values():
            if isinstance(value, dict) and value.get("__fixture__") not in {"callable_object_noop"}:
                check.errors.append(f"executable_acceptance_source_isolation_unknown_fixture:{module_name}")
    return check


def _check_dependency_extraction_policy(catalogs: dict[str, Any]) -> _Check:
    check = _Check("dependency_extraction_policy_integrity")
    policy = dict(catalogs["dependency_extraction_policy"])
    unsafe_calls = {str(item) for item in list(policy.get("unsafe_call_roots") or [])}
    safe_calls = {str(item) for item in list(policy.get("safe_call_roots") or [])}
    safe_bare = {str(item) for item in list(policy.get("safe_bare_calls") or [])}
    for name in sorted(unsafe_calls & (safe_calls | safe_bare)):
        check.errors.append(f"dependency_extraction_policy_conflicting_call_root:{name}")
    return check


def _check_pypi_archetype_rules(catalogs: dict[str, Any]) -> _Check:
    check = _Check("pypi_archetype_kb_integrity")
    rules = [dict(row) for row in list(catalogs["pypi_archetype_rules"])]
    first_slices = {str(row.get("first_slice") or "") for row in rules}
    if len(first_slices) != len(rules):
        check.warnings.append("pypi_archetype_kb_reuses_first_slice")
    return check


def _check_ir_backlog_policy(catalogs: dict[str, Any]) -> _Check:
    check = _Check("system_knowledge_ir_backlog_policy_integrity")
    categories = dict(dict(catalogs["ir_backlog_policy"]).get("categories") or {})
    required = {"purpose", "public_interfaces", "behavior_contracts", "architecture_slices", "acceptance_tests", "data_artifacts"}
    for category in sorted(required - set(categories)):
        check.errors.append(f"ir_backlog_policy_missing_category:{category}")
    return check


def _check_project_probe_env_policy(catalogs: dict[str, Any]) -> _Check:
    check = _Check("project_probe_env_policy_integrity")
    policy = dict(catalogs["project_probe_env_policy"])
    package_map = dict(policy.get("package_to_module") or {})
    low_risk = {str(item) for item in list(policy.get("low_risk_allowlist") or [])}
    native = {str(item) for item in list(policy.get("native_or_compiled") or [])}
    wheel = {str(item) for item in list(policy.get("wheel_only_native_allowlist") or [])}
    if len(package_map) != len({str(key).lower() for key in package_map}):
        check.errors.append("project_probe_env_policy_duplicate:package_to_module")
    if low_risk & native:
        check.errors.append("project_probe_env_policy_overlap:low_risk_and_native")
    for package in sorted(wheel - native):
        check.errors.append(f"project_probe_env_policy_wheel_not_native:{package}")
    return check


def _check_technical_spec_policy(catalogs: dict[str, Any]) -> _Check:
    check = _Check("technical_spec_policy_integrity")
    policy = dict(catalogs["technical_spec_policy"])
    if policy.get("context_only_source_path_tokens"):
        check.warnings.append("technical_spec_policy_deprecated:context_only_source_path_tokens")
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
    review = dict(policy.get("semantic_review_override") or {})
    for field_name in ("enabled", "min_candidate_score", "allowed_statuses", "required_reason_tokens", "required_checks"):
        if field_name not in review:
            check.errors.append(f"technical_spec_policy_missing:semantic_review_override.{field_name}")
    shape = dict(policy.get("architecture_shape_score") or {})
    if not shape.get("positive_source_tokens") or not shape.get("negative_source_tokens"):
        check.errors.append("technical_spec_policy_missing:architecture_shape_score.tokens")
    reselection = dict(policy.get("first_slice_reselection") or {})
    for field_name in (
        "execution_feedback_enabled",
        "execution_feedback_max_iterations",
        "execution_rejection_reasons",
    ):
        if field_name not in reselection:
            check.errors.append(f"technical_spec_policy_missing:first_slice_reselection.{field_name}")
    if int(reselection.get("execution_feedback_max_iterations") or 0) < 1:
        check.errors.append("technical_spec_policy_invalid:first_slice_reselection.execution_feedback_max_iterations")
    if not reselection.get("execution_rejection_reasons"):
        check.errors.append("technical_spec_policy_invalid:first_slice_reselection.execution_rejection_reasons")
    return check


def _check_architecture_decision_policy(catalogs: dict[str, Any]) -> _Check:
    check = _Check("architecture_decision_policy_integrity")
    policy = dict(catalogs["architecture_decision_policy"])
    fallback_archetype = dict(policy.get("fallback_archetype") or {})
    fallback_slice = dict(policy.get("fallback_slice") or {})
    source_selection = dict(policy.get("source_selection") or {})
    role_source = dict(dict(catalogs.get("role_source_policy") or {}).get("implementation_target_policy") or {})
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
    shared_context_tokens = {"/docs/", "/examples/", "/scripts/", "/test/", "/tests/", "/tools/"}
    architecture_tokens = {str(item) for item in list(source_selection.get("context_only_path_tokens") or [])}
    role_source_tokens = {str(item) for item in list(role_source.get("context_only_path_tokens") or [])}
    for token in sorted(shared_context_tokens - architecture_tokens):
        check.errors.append(f"architecture_decision_policy_missing_shared_context_token:{token}")
    for token in sorted(shared_context_tokens - role_source_tokens):
        check.errors.append(f"role_source_policy_missing_shared_context_token:{token}")
    callable_fallback = dict(source_selection.get("callable_transform_fallback") or {})
    for field_name in (
        "symbol_contains_any",
        "path_contains_any",
        "excluded_symbol_prefixes",
        "excluded_path_tokens",
        "allow_contract_profile_without_path_match",
        "pathless_allowed_contract_profiles",
    ):
        if not callable_fallback.get(field_name):
            check.errors.append(f"architecture_decision_policy_missing:source_selection.callable_transform_fallback.{field_name}")
    return check
