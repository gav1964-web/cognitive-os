"""Predicate helpers for foundation semantic quality checks."""

from __future__ import annotations

import re
from typing import Any

from .semantic_target_profiles import matching_profiles


def domain_profile_is_usable(profile: dict[str, Any], summary: dict[str, Any], *, policy: dict[str, Any]) -> bool:
    profile_policy = dict(policy.get("domain_profile") or {})
    kind = str(profile.get("kind") or "")
    generic_kind = str(profile_policy.get("generic_kind") or "generic")
    if kind and kind != generic_kind:
        return bool(profile.get("evidence")) and float(profile.get("confidence") or 0.0) >= float(profile_policy.get("minimum_confidence") or 0.55)
    frameworks = summary.get("frameworks") or []
    entrypoints = summary.get("entrypoints") or []
    allowed_entrypoints = int(profile_policy.get("generic_allowed_when_no_frameworks_and_entrypoints_lte") or 1)
    return not frameworks and len(entrypoints) <= allowed_entrypoints


def architecture_uses_domain_profile(profile: dict[str, Any], project_profile: dict[str, Any], *, policy: dict[str, Any]) -> bool:
    architect_policy = dict(policy.get("architect") or {})
    kind = str(profile.get("kind") or "")
    archetype = str(project_profile.get("archetype") or "")
    carried = dict(project_profile.get("domain_profile") or {})
    carried_kind = str(project_profile.get("domain_profile_kind") or carried.get("kind") or "")
    generic_archetypes = {str(item) for item in architect_policy.get("generic_archetypes", ["", "generic"])}
    if not kind or kind in generic_archetypes:
        return archetype not in generic_archetypes
    return kind == carried_kind or kind == archetype or kind in archetype or archetype in kind


def extraction_plan_is_actionable(readiness: dict[str, Any], *, policy: dict[str, Any]) -> bool:
    project_policy = dict(policy.get("project_analyzer") or {})
    plan = dict(readiness.get("minimal_extraction_plan") or {})
    rows = list(plan.get("capabilities_to_extract") or [])
    if rows:
        return all(isinstance(row, dict) and row.get("capability") and row.get("reason") for row in rows[:3])
    safe_blockers = {str(item) for item in project_policy.get("safe_blockers", ["no_safe_python_candidate"])}
    return bool(safe_blockers & {str(item) for item in list(plan.get("blocked_by") or [])})


def evidence_summary_is_source_backed(content: dict[str, Any], readiness: dict[str, Any], *, policy: dict[str, Any]) -> bool:
    project_policy = dict(policy.get("project_analyzer") or {})
    evidence = dict(content.get("evidence_summary") or {})
    refs = [str(item) for item in list(evidence.get("source_refs") or []) if item]
    if len(refs) >= int(project_policy.get("minimum_source_refs") or 3):
        return True
    claims = list(readiness.get("evidence_claims") or [])
    return len([row for row in claims if isinstance(row, dict) and row.get("source")]) >= int(project_policy.get("minimum_evidence_claims") or 3)


def adr_targets(adr: dict[str, Any]) -> set[str]:
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


def first_slice_targets(adr: dict[str, Any]) -> set[str]:
    first_slice = dict(adr.get("first_slice_contract") or {})
    return {str(item) for item in list(first_slice.get("targets") or []) if item}


def target_in_refs(target: str, refs: set[str]) -> bool:
    normalized = normalize_source_ref(target)
    return bool(normalized) and any(normalized == normalize_source_ref(ref) for ref in refs)


def risks_are_actionable(rows: object, *, policy: dict[str, Any]) -> bool:
    if not isinstance(rows, list) or not rows:
        return False
    return all(
        isinstance(row, dict)
        and specific(row.get("description") or row.get("risk"), policy=policy)
        and (row.get("mitigation") or row.get("evidence_source") or row.get("source"))
        for row in rows[:5]
    )


def ledger_is_usable(value: object) -> bool:
    ledger = dict(value or {})
    facts = list(ledger.get("facts") or [])
    judgments = list(ledger.get("judgments") or [])
    return bool(facts and judgments) and all(isinstance(row, dict) and row.get("claim") for row in facts[:3]) and all(
        isinstance(row, dict) and row.get("judgment") and row.get("validation_gate") for row in judgments[:3]
    )


def contract_shapes_specific(contract: dict[str, Any], *, policy: dict[str, Any]) -> bool:
    if contract.get("contract_family"):
        return isinstance(contract.get("input_contract"), dict) and bool(contract.get("output_contract"))
    spec_policy = dict(policy.get("spec_writer") or {})
    weak_shapes = {str(item).strip().lower() for item in spec_policy.get("weak_contract_shapes", ["", "any", "none", "object"])}
    values = list(dict(contract.get("input_contract") or {}).values()) + list(dict(contract.get("output_contract") or {}).values())
    return bool(values) and all(str(value).strip().lower() not in weak_shapes for value in values)


def side_effects_have_policy(contract: dict[str, Any], *, policy: dict[str, Any]) -> bool:
    side_effects = dict(contract.get("side_effects") or {})
    declared = list(side_effects.get("declared") or [])
    if not declared:
        return True
    side_effect_policy = dict(policy.get("side_effect_policy") or {})
    fields = [str(item) for item in side_effect_policy.get("accepted_policy_fields", [])]
    return any(side_effects.get(field) for field in fields)


def requirements_usable(rows: object, *, policy: dict[str, Any]) -> bool:
    spec_policy = dict(policy.get("spec_writer") or {})
    minimum = int(spec_policy.get("minimum_requirements") or 3)
    return isinstance(rows, list) and len(rows) >= minimum and all(isinstance(row, dict) and specific(row.get("statement"), policy=policy) for row in rows[:minimum])


def acceptance_usable(rows: object, *, policy: dict[str, Any]) -> bool:
    spec_policy = dict(policy.get("spec_writer") or {})
    minimum = int(spec_policy.get("minimum_acceptance_criteria") or 3)
    return isinstance(rows, list) and len(rows) >= minimum and all(
        isinstance(row, dict) and specific(row.get("criterion"), policy=policy) and specific(row.get("verification"), policy=policy) for row in rows[:minimum]
    )


def traceability_usable(rows: object, *, policy: dict[str, Any]) -> bool:
    spec_policy = dict(policy.get("spec_writer") or {})
    minimum = int(spec_policy.get("minimum_traceability_rows") or 3)
    return isinstance(rows, list) and len(rows) >= minimum and all(
        isinstance(row, dict) and row.get("source") and row.get("acceptance_id") for row in rows[:minimum]
    )


def human_review_material_present(spec: dict[str, Any]) -> bool:
    review = dict(spec.get("human_review") or {})
    return (
        bool(review.get("decision_points"))
        and bool(review.get("release_note"))
        and isinstance(review.get("open_questions"), list)
        and bool(spec.get("non_goals") or review.get("non_goals"))
    )


def evidence_bound_no_safe_candidate(spec: dict[str, Any]) -> bool:
    contract = dict(spec.get("extraction_contract") or {})
    request = dict(spec.get("first_slice_reselection_request") or {})
    outcome = dict(request.get("outcome") or {})
    return bool(
        contract.get("status") == "blocked_no_safe_candidate"
        and not contract.get("candidate")
        and request.get("status") == "required"
        and request.get("terminal") is True
        and request.get("resolution_status") == "exhausted"
        and outcome.get("status") == "exhausted"
        and outcome.get("authority") == "architect"
        and int(outcome.get("expanded_candidate_count") or 0) > 0
        and "environment_ready_candidate_count" in outcome
        and isinstance(outcome.get("candidate_viability"), list)
        and int(outcome.get("semantic_qualified_candidate_count") or 0) == 0
        and not list(outcome.get("selected_targets") or [])
    )


def purpose_avoids_marketing_blurb(value: object, *, policy: dict[str, Any]) -> bool:
    project_policy = dict(policy.get("project_analyzer") or {})
    text = without_machine_refs(str(value or "")).lower()
    markers = [str(item).lower() for item in project_policy.get("marketing_purpose_markers", [])]
    return bool(text.strip()) and not any(marker in text for marker in markers)


def purpose_is_specific(scope: dict[str, Any], content: dict[str, Any], *, policy: dict[str, Any]) -> bool:
    purpose = scope.get("main_task")
    if specific(purpose, policy=policy):
        return True
    text = flatten({"purpose": purpose, "profile": scope.get("domain_profile"), "evidence": content.get("evidence_summary")}).lower()
    project_policy = dict(policy.get("project_analyzer") or {})
    markers = {str(item).lower() for item in project_policy.get("purpose_domain_markers", [])}
    hits = {marker for marker in markers if marker in text}
    minimum = int(project_policy.get("purpose_domain_marker_min_hits") or 2)
    return len(str(purpose or "").strip()) >= 32 and len(hits) >= minimum and evidence_summary_is_source_backed(content, {}, policy=policy)


def without_machine_refs(text: str) -> str:
    text = re.sub(r"\[!\[[^\]]*\]\([^)]+\)\]\([^)]+\)", " ", text)
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", " ", text)
    text = re.sub(r"https?://\S+", " ", text)
    return re.sub(r"\bbadge\w*\b", " ", text, flags=re.IGNORECASE)


def generic_profile_not_masking_library_domain(profile: dict[str, Any], content: dict[str, Any], *, policy: dict[str, Any]) -> bool:
    profile_policy = dict(policy.get("domain_profile") or {})
    kind = str(profile.get("kind") or "")
    if kind and kind != str(profile_policy.get("generic_kind") or "generic"):
        return True
    project_policy = dict(policy.get("project_analyzer") or {})
    answers = dict(content.get("answers") or {})
    scope = dict(answers.get("1_scope") or {})
    execution = dict(answers.get("2_execution") or {})
    capabilities = dict(answers.get("3_capabilities") or {})
    text = flatten(
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


def first_slice_not_generic_when_domain_cues_exist(first_slice: dict[str, Any], project: dict[str, Any], *, policy: dict[str, Any]) -> bool:
    architect_policy = dict(policy.get("architect") or {})
    name = str(first_slice.get("name") or first_slice.get("slice_id") or "").lower()
    generic_names = {str(item).lower() for item in architect_policy.get("generic_first_slice_names", [])}
    if name not in generic_names:
        return True
    targets = [str(item) for item in list(first_slice.get("targets", []) or []) if item]
    markers = [str(item).lower() for item in architect_policy.get("domain_slice_markers", [])]
    minimum = int(architect_policy.get("domain_slice_marker_min_hits") or 1)
    slice_text = flatten({"name": name, "summary": first_slice.get("summary"), "rationale": first_slice.get("rationale")}).lower()
    if any(target_has_semantic_contract(target) for target in targets):
        return len({marker for marker in markers if marker in slice_text}) >= min(1, minimum)
    content = dict(project.get("content") or project)
    answers = dict(content.get("answers") or {})
    scope = dict(answers.get("1_scope") or {})
    execution = dict(answers.get("2_execution") or {})
    capabilities = dict(answers.get("3_capabilities") or {})
    text = flatten(
        {
            "main_task": scope.get("main_task"),
            "supported_scenarios": scope.get("supported_scenarios"),
            "execution": execution.get("primary_execution_path") or execution.get("pipeline_candidate"),
            "capabilities": capabilities.get("atomic_reusable_capabilities") or capabilities.get("pure_transforms"),
        }
    ).lower()
    hits = {marker for marker in markers if marker in text}
    return len(hits) < minimum


def target_has_semantic_contract(target: str) -> bool:
    normalized = normalize_source_ref(target)
    return any(profile.get("contract_family") for profile in matching_profiles(normalized))


def check(code: str, passed: bool) -> dict[str, Any]:
    return {"code": code, "passed": bool(passed)}


def score(checks: list[dict[str, Any]], *, role: str, policy: dict[str, Any]) -> float:
    weights = dict(dict(policy.get(role) or {}).get("check_weights") or {})
    total = 0.0
    passed = 0.0
    for check_row in checks:
        weight = float(weights.get(str(check_row.get("code") or ""), 1.0) or 1.0)
        total += weight
        if check_row["passed"]:
            passed += weight
    return round(10.0 * passed / max(1.0, total), 2)


def specific(value: object, *, policy: dict[str, Any]) -> bool:
    specific_policy = dict(policy.get("specific_text") or {})
    text = str(value or "").strip()
    if len(text) < int(specific_policy.get("min_length") or 32):
        return False
    generic = tuple(str(item).lower() for item in specific_policy.get("generic_phrases", []))
    return not any(token in text.lower() for token in generic)


def looks_like_source(value: object, *, policy: dict[str, Any]) -> bool:
    source_policy = dict(policy.get("source_reference") or {})
    text = str(value or "")
    return bool(
        text
        and (
            any(str(token) in text for token in source_policy.get("tokens", []))
            or any(text.endswith(str(suffix)) for suffix in source_policy.get("suffixes", []))
        )
    )


def flatten(value: object) -> str:
    if isinstance(value, dict):
        return " ".join(flatten(item) for item in value.values())
    if isinstance(value, list):
        return " ".join(flatten(item) for item in value)
    return str(value or "")


def normalize_source_ref(value: object) -> str:
    text = str(value or "").strip().replace("\\", "/")
    if "(" in text and text.endswith(")"):
        text = text.rsplit("(", 1)[0].strip()
    return text
