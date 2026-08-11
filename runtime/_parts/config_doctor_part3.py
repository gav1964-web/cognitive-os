from __future__ import annotations

from typing import Any

from runtime._parts.config_doctor_part1 import _Check


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
