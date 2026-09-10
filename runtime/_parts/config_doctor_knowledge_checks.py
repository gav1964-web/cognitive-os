from __future__ import annotations

from typing import Any

from runtime._parts.config_doctor_common import _Check


def _check_project_development_boundary_knowledge(catalogs: dict[str, Any]) -> _Check:
    check = _Check("project_development_boundary_knowledge_integrity")
    profiles_payload = dict(catalogs["project_development_boundary_profiles"])
    contrast_payload = dict(catalogs["project_development_source_contrasts"])
    profiles = [dict(row) for row in profiles_payload.get("profiles") or []]
    non_fallback = [row for row in profiles if row.get("fallback") is not True]
    hypothesis_kinds = {
        str(row.get("hypothesis_kind") or row.get("id") or "") for row in non_fallback
    }
    policy_kinds = set(
        dict(catalogs["project_development_policy"].get("feedback_policy") or {}).get(
            "allowed_hypothesis_kinds"
        ) or []
    )
    if hypothesis_kinds != policy_kinds:
        check.errors.append("project_development_boundary_knowledge_hypothesis_kind_drift")
    promotion = dict(profiles_payload.get("promotion_policy") or {})
    expected_thresholds = {
        "active_kb_requires_promotion": True,
        "minimum_projects": 3,
        "minimum_cases": 5,
        "minimum_blind_cases": 2,
        "minimum_independent_reports": 2,
    }
    if promotion != expected_thresholds:
        check.errors.append("project_development_boundary_knowledge_invalid_promotion_thresholds")
    paired_kinds = {
        str(row.get("hypothesis_kind") or row.get("id") or "")
        for row in non_fallback
        if any(
            dict(rule or {}).get("kind") == "paired_shape"
            for rule in dict(row.get("requirement_rules") or {}).values()
        )
    }
    contrasts = [dict(row) for row in contrast_payload.get("contrasts") or []]
    contrast_kinds = [str(row.get("hypothesis_kind") or "") for row in contrasts]
    if set(contrast_kinds) != paired_kinds or len(contrast_kinds) != len(set(contrast_kinds)):
        check.errors.append("project_development_boundary_knowledge_contrast_profile_drift")
    _check_boundary_profile_evidence(profiles, check)
    _check_boundary_contrast_evidence(contrasts, check)
    bounded = dict(
        dict(
            dict(catalogs["project_development_policy"].get("feedback_policy") or {}).get(
                "replan_revision"
            ) or {}
        ).get("bounded_experiment") or {}
    )
    if "source_contrasts" in bounded:
        check.errors.append("project_development_policy_embeds_source_contrasts")
    return check


def _check_boundary_profile_evidence(profiles: list[dict[str, Any]], check: _Check) -> None:
    for row in profiles:
        profile_id = str(row.get("id") or "")
        evidence = dict(row.get("evidence_state") or {})
        if row.get("status") == "active" and evidence.get("promotion_ready") is not True:
            check.errors.append(
                f"project_development_boundary_knowledge_unproven_active_profile:{profile_id}"
            )


def _check_boundary_contrast_evidence(contrasts: list[dict[str, Any]], check: _Check) -> None:
    for row in contrasts:
        contrast_id = str(row.get("contrast_id") or "")
        digest = str(row.get("sha256") or "")
        if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest.lower()):
            check.errors.append(
                f"project_development_boundary_knowledge_invalid_digest:{contrast_id}"
            )
        if not dict(row.get("expected_facts") or {}):
            check.errors.append(
                f"project_development_boundary_knowledge_missing_expected_facts:{contrast_id}"
            )
        if dict(row.get("provenance") or {}).get("kb_promotion_evidence") is not False:
            check.errors.append(
                f"project_development_boundary_knowledge_illegal_promotion_evidence:{contrast_id}"
            )


def _check_exception_pickle_reconstruction_knowledge(catalogs: dict[str, Any]) -> _Check:
    check = _Check("exception_pickle_reconstruction_knowledge_integrity")
    catalog = dict(catalogs["exception_pickle_reconstruction_patterns"])
    if catalog.get("schema_version") != "exception_pickle_reconstruction_patterns.v1":
        check.errors.append("exception_pickle_reconstruction_knowledge_invalid_schema")
    if catalog.get("status") not in {"active", "absent"}:
        check.errors.append("exception_pickle_reconstruction_knowledge_invalid_status")
    if catalog.get("status") != "active":
        return check
    _check_exception_pickle_operator(catalog, check)
    safety = dict(catalog.get("safety") or {})
    if safety.get("source_apply_allowed") is not False:
        check.errors.append("exception_pickle_reconstruction_knowledge_allows_source_apply")
    if safety.get("automatic_runtime_mutation_allowed") is not False:
        check.errors.append("exception_pickle_reconstruction_knowledge_allows_runtime_mutation")
    if safety.get("requires_sandbox_patch") is not True:
        check.errors.append("exception_pickle_reconstruction_knowledge_missing_sandbox_gate")
    if safety.get("requires_semantic_replay") is not True:
        check.errors.append("exception_pickle_reconstruction_knowledge_missing_semantic_gate")
    evidence = dict(catalog.get("promotion_evidence") or {})
    if len(list(evidence.get("supervised_reports") or [])) < 3:
        check.errors.append("exception_pickle_reconstruction_knowledge_insufficient_supervised_reports")
    if len(list(evidence.get("autonomous_reports") or [])) < 1:
        check.errors.append("exception_pickle_reconstruction_knowledge_missing_autonomous_report")
    if int(evidence.get("holdout_project_count") or 0) < 25:
        check.errors.append("exception_pickle_reconstruction_knowledge_weak_holdout_breadth")
    return check


def _check_exception_pickle_operator(catalog: dict[str, Any], check: _Check) -> None:
    operator = dict(catalog.get("operator") or {})
    expected = {
        "id": "preserve_exception_constructor_reconstruction",
        "status": "validated_active",
        "hypothesis_kind": "exception_pickle_reconstruction_boundary",
        "reconstruction_method": "__reduce__",
        "state_strategy": "reuse_direct_assignments",
    }
    for field_name, value in expected.items():
        if operator.get(field_name) != value:
            check.errors.append(
                f"exception_pickle_reconstruction_knowledge_invalid_operator:{field_name}"
            )
    applicability = dict(operator.get("applicability") or {})
    required_applicability = {
        "required_constructor_inputs_must_be_stored_on_self": True,
        "maximum_required_constructor_inputs": 4,
        "existing_reconstruction_hook_blocks": True,
        "single_class_constructor_target": True,
        "generated_function_stubs_forbidden": True,
    }
    for field_name, value in required_applicability.items():
        if applicability.get(field_name) != value:
            check.errors.append(
                f"exception_pickle_reconstruction_knowledge_invalid_applicability:{field_name}"
            )


def _check_project_native_cli_repair_knowledge(catalogs: dict[str, Any]) -> _Check:
    check = _Check("project_native_cli_repair_knowledge_integrity")
    catalog = dict(catalogs["project_native_cli_failure_repair_patterns"])
    if catalog.get("schema_version") != "project_native_cli_failure_repair_patterns.v1":
        check.errors.append("project_native_cli_repair_knowledge_invalid_schema")
    lifecycle = str(catalog.get("status") or "")
    if lifecycle not in {"staged", "threshold_met_awaiting_explicit_promotion", "active"}:
        check.errors.append("project_native_cli_repair_knowledge_invalid_lifecycle")
    promotion = dict(catalog.get("promotion_policy") or {})
    required_policy = {
        "automatic_promotion": False,
        "source_apply_allowed": False,
        "project_stratum": "cli_local_tool",
    }
    for field_name, expected in required_policy.items():
        if promotion.get(field_name) != expected:
            check.errors.append(
                f"project_native_cli_repair_knowledge_invalid_policy:{field_name}"
            )
    if int(promotion.get("minimum_independent_lineages") or 0) < 3:
        check.errors.append("project_native_cli_repair_knowledge_weak_lineage_threshold")
    if int(promotion.get("minimum_project_native_transformations") or 0) < 3:
        check.errors.append("project_native_cli_repair_knowledge_weak_transformation_threshold")
    known_operations = {
        str(dict(recipe or {}).get("operation_kind") or "")
        for recipe in dict(catalogs["patch_synthesis_policy"].get("recipes") or {}).values()
    }
    patterns = [dict(row) for row in catalog.get("patterns") or []]
    pattern_ids = [str(row.get("id") or "") for row in patterns]
    if not patterns or "" in pattern_ids or len(pattern_ids) != len(set(pattern_ids)):
        check.errors.append("project_native_cli_repair_knowledge_invalid_pattern_ids")
    for pattern in patterns:
        _check_cli_repair_pattern(pattern, lifecycle, known_operations, check)
    return check


def _check_cli_repair_pattern(
    pattern: dict[str, Any],
    lifecycle: str,
    known_operations: set[str],
    check: _Check,
) -> None:
    pattern_id = str(pattern.get("id") or "")
    expected_status = "validated_active" if lifecycle == "active" else "validated_staged"
    expected_ready = lifecycle == "active"
    if pattern.get("status") != expected_status or pattern.get("promotion_ready") is not expected_ready:
        check.errors.append(
            f"project_native_cli_repair_knowledge_illegal_pattern_status:{pattern_id}"
        )
    blockers = list(pattern.get("promotion_blockers") or [])
    if lifecycle != "active" and not blockers:
        check.errors.append(
            f"project_native_cli_repair_knowledge_missing_blockers:{pattern_id}"
        )
    if lifecycle == "active" and blockers:
        check.errors.append(
            f"project_native_cli_repair_knowledge_active_pattern_has_blockers:{pattern_id}"
        )
    if str(pattern.get("operator_id") or "") not in known_operations:
        check.errors.append(
            f"project_native_cli_repair_knowledge_unknown_operator:{pattern_id}"
        )


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
    _check_project_evolution_chosen_and_lanes(policy, check)
    _check_project_evolution_gates(policy, check)
    return check


def _check_project_evolution_chosen_and_lanes(policy: dict[str, Any], check: _Check) -> None:
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


def _check_project_evolution_gates(policy: dict[str, Any], check: _Check) -> None:
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
    if int(section.get("source_snippet_max_chars") or 0) < 900:
        check.errors.append("role_source_policy_invalid:source_snippet_max_chars")
    scope = dict(policy.get("scope_selection_policy") or {})
    for field_name in (
        "candidate_excluded_dirs",
        "candidate_noise_parts",
        "candidate_noise_suffixes",
        "disfavored_roots",
        "manifest_names",
        "preferred_roots",
        "auto_selector_strategy_order",
        "syntax_fixture_roots",
    ):
        if not scope.get(field_name):
            check.errors.append(f"role_source_policy_missing_scope_field:{field_name}")
    required_scope_roots = {"src", "lib"}
    actual_scope_roots = {str(item) for item in list(scope.get("preferred_roots") or [])}
    for token in sorted(required_scope_roots - actual_scope_roots):
        check.errors.append(f"role_source_policy_missing_preferred_scope_root:{token}")
    return check
