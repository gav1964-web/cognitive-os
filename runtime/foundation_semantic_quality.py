"""Semantic usefulness checks for Project Analyzer -> Architect -> SpecWriter."""

from __future__ import annotations

from typing import Any

from .foundation_semantic_quality_policy import load_foundation_semantic_quality_policy
from .foundation_source_context_quality import source_context_is_sufficient
from .foundation_semantic_quality_predicates import (
    acceptance_usable as _acceptance_usable,
    adr_targets as _adr_targets,
    architecture_uses_domain_profile as _architecture_uses_domain_profile,
    check as _check,
    contract_shapes_specific as _contract_shapes_specific,
    domain_profile_is_usable as _domain_profile_is_usable,
    evidence_bound_no_safe_candidate as _evidence_bound_no_safe_candidate,
    evidence_summary_is_source_backed as _evidence_summary_is_source_backed,
    extraction_plan_is_actionable as _extraction_plan_is_actionable,
    first_slice_not_generic_when_domain_cues_exist as _first_slice_not_generic_when_domain_cues_exist,
    first_slice_targets as _first_slice_targets,
    flatten as _flatten,
    generic_profile_not_masking_library_domain as _generic_profile_not_masking_library_domain,
    human_review_material_present as _human_review_material_present,
    ledger_is_usable as _ledger_is_usable,
    looks_like_source as _looks_like_source,
    purpose_avoids_marketing_blurb as _purpose_avoids_marketing_blurb,
    purpose_is_specific as _purpose_is_specific,
    requirements_usable as _requirements_usable,
    risks_are_actionable as _risks_are_actionable,
    score as _score,
    side_effects_have_policy as _side_effects_have_policy,
    specific as _specific,
    target_in_refs as _target_in_refs,
    traceability_usable as _traceability_usable,
)
from .problem_outcome_contract import validate_problem_outcome_contract


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
    ] + _causal_role_checks("project_analyzer", project=project)


def _architect_checks(project: dict[str, Any], adr: dict[str, Any], spec: dict[str, Any], *, policy: dict[str, Any]) -> list[dict[str, Any]]:
    content = dict(project.get("content") or project)
    scope = dict(dict(content.get("answers") or {}).get("1_scope") or {})
    profile = dict(scope.get("domain_profile") or {})
    synthesis = dict(adr.get("architecture_synthesis") or {})
    project_profile = dict(synthesis.get("project_profile") or {})
    first_slice = dict(adr.get("first_slice_contract") or {})
    brief = dict(adr.get("spec_writer_brief") or {})
    spec_target = str(dict(spec.get("extraction_contract") or {}).get("candidate") or "")
    evidence_bound_stop = _evidence_bound_no_safe_candidate(spec)
    adr_targets = _adr_targets(adr)
    first_slice_targets = _first_slice_targets(adr)
    architect_policy = dict(policy.get("architect") or {})
    return [
        _check("decision_summary_specific", _specific(adr.get("decision_summary"), policy=policy)),
        _check("domain_profile_carried_to_architecture", _architecture_uses_domain_profile(profile, project_profile, policy=policy)),
        _check("first_slice_not_generic_when_domain_cues_exist", _first_slice_not_generic_when_domain_cues_exist(first_slice, project, policy=policy)),
        _check("options_and_rejections_have_tradeoffs", len(adr.get("architecture_options") or []) >= int(architect_policy.get("minimum_options") or 2) and bool(adr.get("rejected_options"))),
        _check("first_slice_is_source_backed", bool(first_slice.get("targets")) and any(_looks_like_source(item, policy=policy) for item in first_slice.get("targets") or [])),
        _check(
            "spec_target_is_within_architect_slice",
            evidence_bound_stop
            or (_target_in_refs(spec_target, first_slice_targets) if first_slice_targets else bool(spec_target) and spec_target in adr_targets),
        ),
        _check("brief_has_contract_and_acceptance_targets", bool(brief.get("contract_targets")) and bool(brief.get("acceptance_targets"))),
        _check("risks_are_actionable", _risks_are_actionable(adr.get("risks"), policy=policy)),
        _check("fact_judgment_ledger_separates_claims", _ledger_is_usable(adr.get("fact_judgment_ledger"))),
        _check("source_context_has_multiple_refs", source_context_is_sufficient(
            content, adr, minimum_refs=int(architect_policy.get("minimum_source_context_refs") or 3)
        )),
        _check("open_questions_and_non_goals_present", isinstance(adr.get("open_questions"), list) and bool(adr.get("non_goals"))),
    ] + _causal_role_checks("architect", project=project, adr=adr)


def _spec_writer_checks(adr: dict[str, Any], spec: dict[str, Any], *, policy: dict[str, Any]) -> list[dict[str, Any]]:
    contract = dict(spec.get("extraction_contract") or {})
    ranked = list(contract.get("ranked_candidates") or [])
    candidate = str(contract.get("candidate") or "")
    evidence_bound_stop = _evidence_bound_no_safe_candidate(spec)
    text = _flatten(spec).lower()
    spec_policy = dict(policy.get("spec_writer") or {})
    negative_tokens = [str(token).lower() for token in spec_policy.get("negative_case_tokens", [])]
    return [
        _check("candidate_ranked_first", evidence_bound_stop or (bool(candidate and ranked) and str(dict(ranked[0]).get("source") or "") == candidate)),
        _check("candidate_backed_by_adr", evidence_bound_stop or _target_in_refs(candidate, _adr_targets(adr))),
        _check("io_contract_shapes_specific", evidence_bound_stop or _contract_shapes_specific(contract, policy=policy)),
        _check("side_effect_policy_or_no_side_effects", _side_effects_have_policy(contract, policy=policy)),
        _check("requirements_and_acceptance_are_implementable", _requirements_usable(spec.get("requirements"), policy=policy) and _acceptance_usable(spec.get("acceptance_criteria"), policy=policy)),
        _check("negative_or_edge_cases_present", any(token in text for token in negative_tokens)),
        _check("traceability_links_sources_to_acceptance", _traceability_usable(spec.get("traceability_table"), policy=policy)),
        _check("work_plan_has_obligations", bool(dict(spec.get("work_plan_contract") or {}).get("obligations"))),
        _check("implementation_handoff_bounded", bool(dict(spec.get("implementation_handoff") or {}).get("patch_scope"))),
        _check("human_review_material_present", _human_review_material_present(spec)),
    ] + _causal_role_checks("spec_writer", adr=adr, spec=spec)


def _causal_role_checks(
    role: str, *, project: dict[str, Any] | None = None,
    adr: dict[str, Any] | None = None, spec: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    artifacts = [project or {}, adr or {}, spec or {}]
    contract = next(
        (dict(row.get("problem_outcome_contract") or {}) for row in artifacts if row.get("problem_outcome_contract")),
        {},
    )
    if not contract:
        return []
    valid = not validate_problem_outcome_contract(contract)
    target = str(contract.get("target") or "")
    if role == "project_analyzer":
        return [
            _check("problem_outcome_contract_valid", valid),
            _check(
                "baseline_failure_is_evidence_bound",
                contract.get("status") == "evidence_bound"
                and bool(contract.get("baseline_failures"))
                and target in set(str(value) for value in contract.get("allowed_targets") or []),
            ),
        ]
    if role == "architect":
        first_slice = dict((adr or {}).get("first_slice_contract") or {})
        repair = dict(contract.get("repair_design") or {})
        return [
            _check("problem_outcome_contract_valid", valid),
            _check("causal_target_selected", _target_in_refs(target, set(first_slice.get("targets") or []))),
            _check("repair_mechanism_explicit", bool(repair.get("mechanism") or repair.get("mutation_contract"))),
        ]
    extraction = dict((spec or {}).get("extraction_contract") or {})
    acceptance_ids = {
        str(row.get("id") or "") for row in (spec or {}).get("acceptance_criteria") or []
        if isinstance(row, dict)
    }
    return [
        _check("problem_outcome_contract_valid", valid),
        _check("causal_target_preserved", _target_in_refs(str(extraction.get("candidate") or ""), {target})),
        _check("baseline_replay_acceptance_present", any(value.startswith("AC-FAILURE-REPLAY") for value in acceptance_ids)),
        _check("causal_regression_acceptance_present", "AC-FAILURE-REGRESSION" in acceptance_ids),
    ]
