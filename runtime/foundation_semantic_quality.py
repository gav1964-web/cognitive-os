"""Semantic usefulness checks for Project Analyzer -> Architect -> SpecWriter."""

from __future__ import annotations

import re
from typing import Any

from .foundation_semantic_quality_policy import load_foundation_semantic_quality_policy
from .semantic_target_profiles import matching_profiles


def evaluate_foundation_semantic_quality(result: dict[str, Any], *, policy: dict[str, Any] | None = None) -> dict[str, Any]:
    policy = policy or load_foundation_semantic_quality_policy()
    artifacts = dict(result.get("artifacts") or {})
    project = dict(artifacts.get("project_map_report") or {})
    adr = dict(artifacts.get("architecture_decision") or {})
    spec = dict(artifacts.get("technical_spec") or {})
    checks = {
        "project_analyzer": _project_analyzer_checks(project, policy=policy),
        "architect": _architect_checks(project, adr, spec, policy=policy),
        "spec_writer": _spec_writer_checks(adr, spec, policy=policy),
    }
    role_scores = {role: _score(rows, role=role, policy=policy) for role, rows in checks.items()}
    warnings = [
        f"{role}.{check['code']}"
        for role, rows in checks.items()
        for check in rows
        if not check["passed"]
    ]
    threshold = float(policy.get("status_threshold") or 8.8)
    return {
        "artifact_type": "FoundationSemanticQualityReport",
        "status": "ok" if min(role_scores.values(), default=0.0) >= threshold else "needs_work",
        "role_scores": role_scores,
        "min_score": round(min(role_scores.values(), default=0.0), 2),
        "warnings": warnings,
        "checks": checks,
    }


def _project_analyzer_checks(project: dict[str, Any], *, policy: dict[str, Any]) -> list[dict[str, Any]]:
    content = dict(project.get("content") or project)
    summary = dict(content.get("summary") or {})
    answers = dict(content.get("answers") or {})
    scope = dict(answers.get("1_scope") or {})
    execution = dict(answers.get("2_execution") or {})
    capabilities = dict(answers.get("3_capabilities") or {})
    contracts = dict(answers.get("4_contracts_data") or {})
    errors = dict(answers.get("5_errors_state_repro") or {})
    readiness = dict(answers.get("6_runtime_extraction_readiness") or {})
    profile = dict(scope.get("domain_profile") or {})
    project_policy = dict(policy.get("project_analyzer") or {})
    return [
        _check("purpose_is_specific", _purpose_is_specific(scope, content, policy=policy)),
        _check("purpose_avoids_marketing_blurb", _purpose_avoids_marketing_blurb(scope.get("main_task"), policy=policy)),
        _check("domain_profile_is_specific_or_evidently_generic", _domain_profile_is_usable(profile, summary, policy=policy)),
        _check("generic_profile_not_masking_library_domain", _generic_profile_not_masking_library_domain(profile, content, policy=policy)),
        _check(
            "scenarios_inputs_outputs_are_rich",
            len(scope.get("supported_scenarios") or []) >= int(project_policy.get("minimum_supported_scenarios") or 2)
            and bool(scope.get("inputs"))
            and bool(scope.get("outputs")),
        ),
        _check("execution_path_has_control_nodes", bool(execution.get("primary_execution_path") or execution.get("central_flow_nodes") or execution.get("pipeline_candidate"))),
        _check("capability_model_has_candidates", bool(capabilities.get("atomic_reusable_capabilities") or capabilities.get("pure_transforms") or dict(readiness.get("minimal_extraction_plan") or {}).get("capabilities_to_extract"))),
        _check("data_contracts_and_weak_zones_present", bool(contracts.get("main_data_structures")) and isinstance(contracts.get("weak_contract_zones"), list)),
        _check("error_state_replay_model_present", bool(errors.get("likely_error_types")) and bool(errors.get("state_to_preserve")) and bool(errors.get("minimal_cognitive_loop"))),
        _check("data_lifecycle_is_multistage", len(readiness.get("data_lifecycle") or []) >= int(project_policy.get("minimum_data_lifecycle_stages") or 3)),
        _check("minimal_extraction_plan_is_actionable", _extraction_plan_is_actionable(readiness, policy=policy)),
        _check("evidence_summary_is_source_backed", _evidence_summary_is_source_backed(content, readiness, policy=policy)),
    ]


def _architect_checks(project: dict[str, Any], adr: dict[str, Any], spec: dict[str, Any], *, policy: dict[str, Any]) -> list[dict[str, Any]]:
    content = dict(project.get("content") or project)
    scope = dict(dict(content.get("answers") or {}).get("1_scope") or {})
    profile = dict(scope.get("domain_profile") or {})
    synthesis = dict(adr.get("architecture_synthesis") or {})
    project_profile = dict(synthesis.get("project_profile") or {})
    first_slice = dict(adr.get("first_slice_contract") or {})
    brief = dict(adr.get("spec_writer_brief") or {})
    spec_target = str(dict(spec.get("extraction_contract") or {}).get("candidate") or "")
    adr_targets = _adr_targets(adr)
    first_slice_targets = _first_slice_targets(adr)
    architect_policy = dict(policy.get("architect") or {})
    return [
        _check("decision_summary_specific", _specific(adr.get("decision_summary"), policy=policy)),
        _check("domain_profile_carried_to_architecture", _architecture_uses_domain_profile(profile, project_profile, policy=policy)),
        _check("first_slice_not_generic_when_domain_cues_exist", _first_slice_not_generic_when_domain_cues_exist(first_slice, project, policy=policy)),
        _check("options_and_rejections_have_tradeoffs", len(adr.get("architecture_options") or []) >= int(architect_policy.get("minimum_options") or 2) and bool(adr.get("rejected_options"))),
        _check("first_slice_is_source_backed", bool(first_slice.get("targets")) and any(_looks_like_source(item, policy=policy) for item in first_slice.get("targets") or [])),
        _check("spec_target_is_within_architect_slice", _target_in_refs(spec_target, first_slice_targets) if first_slice_targets else bool(spec_target) and spec_target in adr_targets),
        _check("brief_has_contract_and_acceptance_targets", bool(brief.get("contract_targets")) and bool(brief.get("acceptance_targets"))),
        _check("risks_are_actionable", _risks_are_actionable(adr.get("risks"), policy=policy)),
        _check("fact_judgment_ledger_separates_claims", _ledger_is_usable(adr.get("fact_judgment_ledger"))),
        _check("source_context_has_multiple_refs", len(dict(adr.get("source_context") or {})) >= int(architect_policy.get("minimum_source_context_refs") or 3)),
        _check("open_questions_and_non_goals_present", isinstance(adr.get("open_questions"), list) and bool(adr.get("non_goals"))),
    ]


def _spec_writer_checks(adr: dict[str, Any], spec: dict[str, Any], *, policy: dict[str, Any]) -> list[dict[str, Any]]:
    contract = dict(spec.get("extraction_contract") or {})
    ranked = list(contract.get("ranked_candidates") or [])
    candidate = str(contract.get("candidate") or "")
    text = _flatten(spec).lower()
    spec_policy = dict(policy.get("spec_writer") or {})
    negative_tokens = [str(token).lower() for token in spec_policy.get("negative_case_tokens", [])]
    return [
        _check("candidate_ranked_first", bool(candidate and ranked) and str(dict(ranked[0]).get("source") or "") == candidate),
        _check("candidate_backed_by_adr", _target_in_refs(candidate, _adr_targets(adr))),
        _check("io_contract_shapes_specific", _contract_shapes_specific(contract, policy=policy)),
        _check("side_effect_policy_or_no_side_effects", _side_effects_have_policy(contract, policy=policy)),
        _check("requirements_and_acceptance_are_implementable", _requirements_usable(spec.get("requirements"), policy=policy) and _acceptance_usable(spec.get("acceptance_criteria"), policy=policy)),
        _check("negative_or_edge_cases_present", any(token in text for token in negative_tokens)),
        _check("traceability_links_sources_to_acceptance", _traceability_usable(spec.get("traceability_table"), policy=policy)),
        _check("work_plan_has_obligations", bool(dict(spec.get("work_plan_contract") or {}).get("obligations"))),
        _check("implementation_handoff_bounded", bool(dict(spec.get("implementation_handoff") or {}).get("patch_scope"))),
        _check("human_review_material_present", _human_review_material_present(spec)),
    ]


def _domain_profile_is_usable(profile: dict[str, Any], summary: dict[str, Any], *, policy: dict[str, Any]) -> bool:
    profile_policy = dict(policy.get("domain_profile") or {})
    kind = str(profile.get("kind") or "")
    generic_kind = str(profile_policy.get("generic_kind") or "generic")
    if kind and kind != generic_kind:
        return bool(profile.get("evidence")) and float(profile.get("confidence") or 0.0) >= float(profile_policy.get("minimum_confidence") or 0.55)
    frameworks = summary.get("frameworks") or []
    entrypoints = summary.get("entrypoints") or []
    allowed_entrypoints = int(profile_policy.get("generic_allowed_when_no_frameworks_and_entrypoints_lte") or 1)
    return not frameworks and len(entrypoints) <= allowed_entrypoints


def _architecture_uses_domain_profile(profile: dict[str, Any], project_profile: dict[str, Any], *, policy: dict[str, Any]) -> bool:
    architect_policy = dict(policy.get("architect") or {})
    kind = str(profile.get("kind") or "")
    archetype = str(project_profile.get("archetype") or "")
    carried = dict(project_profile.get("domain_profile") or {})
    carried_kind = str(project_profile.get("domain_profile_kind") or carried.get("kind") or "")
    generic_archetypes = {str(item) for item in architect_policy.get("generic_archetypes", ["", "generic"])}
    if not kind or kind in generic_archetypes:
        return archetype not in generic_archetypes
    return kind == carried_kind or kind == archetype or kind in archetype or archetype in kind


def _extraction_plan_is_actionable(readiness: dict[str, Any], *, policy: dict[str, Any]) -> bool:
    project_policy = dict(policy.get("project_analyzer") or {})
    plan = dict(readiness.get("minimal_extraction_plan") or {})
    rows = list(plan.get("capabilities_to_extract") or [])
    if rows:
        return all(isinstance(row, dict) and row.get("capability") and row.get("reason") for row in rows[:3])
    safe_blockers = {str(item) for item in project_policy.get("safe_blockers", ["no_safe_python_candidate"])}
    return bool(safe_blockers & {str(item) for item in list(plan.get("blocked_by") or [])})


def _evidence_summary_is_source_backed(content: dict[str, Any], readiness: dict[str, Any], *, policy: dict[str, Any]) -> bool:
    project_policy = dict(policy.get("project_analyzer") or {})
    evidence = dict(content.get("evidence_summary") or {})
    refs = [str(item) for item in list(evidence.get("source_refs") or []) if item]
    if len(refs) >= int(project_policy.get("minimum_source_refs") or 3):
        return True
    claims = list(readiness.get("evidence_claims") or [])
    return len([row for row in claims if isinstance(row, dict) and row.get("source")]) >= int(project_policy.get("minimum_evidence_claims") or 3)


def _adr_targets(adr: dict[str, Any]) -> set[str]:
    first_slice = dict(adr.get("first_slice_contract") or {})
    brief = dict(adr.get("spec_writer_brief") or {})
    return {
        str(item)
        for item in [
            *list(first_slice.get("targets") or []),
            *list(brief.get("files_or_symbols") or []),
        ]
        if item
    }


def _first_slice_targets(adr: dict[str, Any]) -> set[str]:
    first_slice = dict(adr.get("first_slice_contract") or {})
    return {str(item) for item in list(first_slice.get("targets") or []) if item}


def _target_in_refs(target: str, refs: set[str]) -> bool:
    normalized = _normalize_source_ref(target)
    return bool(normalized) and any(normalized == _normalize_source_ref(ref) for ref in refs)


def _risks_are_actionable(rows: object, *, policy: dict[str, Any]) -> bool:
    if not isinstance(rows, list) or not rows:
        return False
    return all(
        isinstance(row, dict)
        and _specific(row.get("description") or row.get("risk"), policy=policy)
        and (row.get("mitigation") or row.get("evidence_source") or row.get("source"))
        for row in rows[:5]
    )


def _ledger_is_usable(value: object) -> bool:
    ledger = dict(value or {})
    facts = list(ledger.get("facts") or [])
    judgments = list(ledger.get("judgments") or [])
    return bool(facts and judgments) and all(isinstance(row, dict) and row.get("claim") for row in facts[:3]) and all(
        isinstance(row, dict) and row.get("judgment") and row.get("validation_gate") for row in judgments[:3]
    )


def _contract_shapes_specific(contract: dict[str, Any], *, policy: dict[str, Any]) -> bool:
    if contract.get("contract_family"):
        return isinstance(contract.get("input_contract"), dict) and bool(contract.get("output_contract"))
    spec_policy = dict(policy.get("spec_writer") or {})
    weak_shapes = {str(item).strip().lower() for item in spec_policy.get("weak_contract_shapes", ["", "any", "none", "object"])}
    values = list(dict(contract.get("input_contract") or {}).values()) + list(dict(contract.get("output_contract") or {}).values())
    return bool(values) and all(str(value).strip().lower() not in weak_shapes for value in values)


def _side_effects_have_policy(contract: dict[str, Any], *, policy: dict[str, Any]) -> bool:
    side_effects = dict(contract.get("side_effects") or {})
    declared = list(side_effects.get("declared") or [])
    if not declared:
        return True
    side_effect_policy = dict(policy.get("side_effect_policy") or {})
    fields = [str(item) for item in side_effect_policy.get("accepted_policy_fields", [])]
    return any(side_effects.get(field) for field in fields)


def _requirements_usable(rows: object, *, policy: dict[str, Any]) -> bool:
    spec_policy = dict(policy.get("spec_writer") or {})
    minimum = int(spec_policy.get("minimum_requirements") or 3)
    return isinstance(rows, list) and len(rows) >= minimum and all(isinstance(row, dict) and _specific(row.get("statement"), policy=policy) for row in rows[:minimum])


def _acceptance_usable(rows: object, *, policy: dict[str, Any]) -> bool:
    spec_policy = dict(policy.get("spec_writer") or {})
    minimum = int(spec_policy.get("minimum_acceptance_criteria") or 3)
    return isinstance(rows, list) and len(rows) >= minimum and all(
        isinstance(row, dict) and _specific(row.get("criterion"), policy=policy) and _specific(row.get("verification"), policy=policy) for row in rows[:minimum]
    )


def _traceability_usable(rows: object, *, policy: dict[str, Any]) -> bool:
    spec_policy = dict(policy.get("spec_writer") or {})
    minimum = int(spec_policy.get("minimum_traceability_rows") or 3)
    return isinstance(rows, list) and len(rows) >= minimum and all(
        isinstance(row, dict) and row.get("source") and row.get("acceptance_id") for row in rows[:minimum]
    )


def _human_review_material_present(spec: dict[str, Any]) -> bool:
    review = dict(spec.get("human_review") or {})
    return (
        bool(review.get("decision_points"))
        and bool(review.get("release_note"))
        and isinstance(review.get("open_questions"), list)
        and bool(spec.get("non_goals") or review.get("non_goals"))
    )


def _purpose_avoids_marketing_blurb(value: object, *, policy: dict[str, Any]) -> bool:
    project_policy = dict(policy.get("project_analyzer") or {})
    text = _without_machine_refs(str(value or "")).lower()
    markers = [str(item).lower() for item in project_policy.get("marketing_purpose_markers", [])]
    return bool(text.strip()) and not any(marker in text for marker in markers)


def _purpose_is_specific(scope: dict[str, Any], content: dict[str, Any], *, policy: dict[str, Any]) -> bool:
    purpose = scope.get("main_task")
    if _specific(purpose, policy=policy):
        return True
    text = _flatten({"purpose": purpose, "profile": scope.get("domain_profile"), "evidence": content.get("evidence_summary")}).lower()
    project_policy = dict(policy.get("project_analyzer") or {})
    markers = {str(item).lower() for item in project_policy.get("purpose_domain_markers", [])}
    hits = {marker for marker in markers if marker in text}
    minimum = int(project_policy.get("purpose_domain_marker_min_hits") or 2)
    return len(str(purpose or "").strip()) >= 32 and len(hits) >= minimum and _evidence_summary_is_source_backed(content, {}, policy=policy)


def _without_machine_refs(text: str) -> str:
    text = re.sub(r"\[!\[[^\]]*\]\([^)]+\)\]\([^)]+\)", " ", text)
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", " ", text)
    text = re.sub(r"https?://\S+", " ", text)
    return re.sub(r"\bbadge\w*\b", " ", text, flags=re.IGNORECASE)


def _generic_profile_not_masking_library_domain(profile: dict[str, Any], content: dict[str, Any], *, policy: dict[str, Any]) -> bool:
    profile_policy = dict(policy.get("domain_profile") or {})
    kind = str(profile.get("kind") or "")
    if kind and kind != str(profile_policy.get("generic_kind") or "generic"):
        return True
    project_policy = dict(policy.get("project_analyzer") or {})
    answers = dict(content.get("answers") or {})
    scope = dict(answers.get("1_scope") or {})
    execution = dict(answers.get("2_execution") or {})
    capabilities = dict(answers.get("3_capabilities") or {})
    text = _flatten(
        {
            "main_task": scope.get("main_task"),
            "supported_scenarios": scope.get("supported_scenarios"),
            "domain_evidence": profile.get("evidence"),
            "execution": execution.get("primary_execution_path") or execution.get("pipeline_candidate"),
            "capabilities": capabilities.get("atomic_reusable_capabilities") or capabilities.get("pure_transforms"),
        }
    ).lower()
    markers = [str(item).lower() for item in project_policy.get("library_domain_markers", [])]
    hits = {marker for marker in markers if marker in text}
    minimum = int(project_policy.get("library_domain_marker_min_hits") or 1)
    return len(hits) < minimum


def _first_slice_not_generic_when_domain_cues_exist(first_slice: dict[str, Any], project: dict[str, Any], *, policy: dict[str, Any]) -> bool:
    architect_policy = dict(policy.get("architect") or {})
    name = str(first_slice.get("name") or first_slice.get("slice_id") or "").lower()
    generic_names = {str(item).lower() for item in architect_policy.get("generic_first_slice_names", [])}
    if name not in generic_names:
        return True
    targets = [str(item) for item in list(first_slice.get("targets", []) or []) if item]
    markers = [str(item).lower() for item in architect_policy.get("domain_slice_markers", [])]
    minimum = int(architect_policy.get("domain_slice_marker_min_hits") or 1)
    slice_text = _flatten({"name": name, "summary": first_slice.get("summary"), "rationale": first_slice.get("rationale")}).lower()
    if any(_target_has_semantic_contract(target) for target in targets):
        return len({marker for marker in markers if marker in slice_text}) >= min(1, minimum)
    content = dict(project.get("content") or project)
    answers = dict(content.get("answers") or {})
    scope = dict(answers.get("1_scope") or {})
    execution = dict(answers.get("2_execution") or {})
    capabilities = dict(answers.get("3_capabilities") or {})
    text = _flatten(
        {
            "main_task": scope.get("main_task"),
            "supported_scenarios": scope.get("supported_scenarios"),
            "execution": execution.get("primary_execution_path") or execution.get("pipeline_candidate"),
            "capabilities": capabilities.get("atomic_reusable_capabilities") or capabilities.get("pure_transforms"),
        }
    ).lower()
    hits = {marker for marker in markers if marker in text}
    return len(hits) < minimum


def _target_has_semantic_contract(target: str) -> bool:
    normalized = _normalize_source_ref(target)
    return any(profile.get("contract_family") for profile in matching_profiles(normalized))


def _check(code: str, passed: bool) -> dict[str, Any]:
    return {"code": code, "passed": bool(passed)}


def _score(checks: list[dict[str, Any]], *, role: str, policy: dict[str, Any]) -> float:
    weights = dict(dict(policy.get(role) or {}).get("check_weights") or {})
    total = 0.0
    passed = 0.0
    for check in checks:
        weight = float(weights.get(str(check.get("code") or ""), 1.0) or 1.0)
        total += weight
        if check["passed"]:
            passed += weight
    return round(10.0 * passed / max(1.0, total), 2)


def _specific(value: object, *, policy: dict[str, Any]) -> bool:
    specific = dict(policy.get("specific_text") or {})
    text = str(value or "").strip()
    if len(text) < int(specific.get("min_length") or 32):
        return False
    generic = tuple(str(item).lower() for item in specific.get("generic_phrases", []))
    return not any(token in text.lower() for token in generic)


def _looks_like_source(value: object, *, policy: dict[str, Any]) -> bool:
    source_policy = dict(policy.get("source_reference") or {})
    text = str(value or "")
    return bool(
        text
        and (
            any(str(token) in text for token in source_policy.get("tokens", []))
            or any(text.endswith(str(suffix)) for suffix in source_policy.get("suffixes", []))
        )
    )


def _flatten(value: object) -> str:
    if isinstance(value, dict):
        return " ".join(_flatten(item) for item in value.values())
    if isinstance(value, list):
        return " ".join(_flatten(item) for item in value)
    return str(value or "")


def _normalize_source_ref(value: object) -> str:
    text = str(value or "").strip().replace("\\", "/")
    if "(" in text and text.endswith(")"):
        text = text.rsplit("(", 1)[0].strip()
    return text
