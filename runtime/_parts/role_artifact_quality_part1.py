from __future__ import annotations

from typing import Any

GENERIC_PHRASES = (
    "improve architecture",
    "make it better",
    "refactor as needed",
    "optimize the code",
    "clean up",
    "best practices",
    "handle everything",
)

def evaluate_role_artifacts(artifacts: dict[str, dict[str, Any]]) -> dict[str, Any]:
    project = dict(artifacts.get("project_map_report", {}))
    adr = dict(artifacts.get("architecture_decision", {}))
    spec = dict(artifacts.get("technical_spec", {}))
    results = {
        "adr": evaluate_architecture_decision(adr),
        "technical_spec": evaluate_technical_spec(spec),
    }
    if project:
        results = {"project_map_report": evaluate_project_map_report(project), **results}
    if artifacts.get("implementation_plan"):
        results["implementation_plan"] = evaluate_implementation_plan(dict(artifacts["implementation_plan"]))
    if artifacts.get("test_plan"):
        results["test_plan"] = evaluate_test_plan(dict(artifacts["test_plan"]))
    if artifacts.get("review_findings"):
        results["review_findings"] = evaluate_review_findings(dict(artifacts["review_findings"]))
    warnings = [f"{name}.{warning}" for name, result in results.items() for warning in result["warnings"]]
    blocking_warnings = [
        f"{name}.{warning}"
        for name, result in results.items()
        for warning in result["warnings"]
        if _blocking_warning(warning)
    ]
    score = _ratio(sum(float(item["score"]) for item in results.values()), len(results))
    return {
        "passed": score >= 0.9 and not blocking_warnings,
        "score": score,
        "results": results,
        "warnings": warnings,
        "blocking_warnings": blocking_warnings,
    }

def evaluate_project_map_report(project: dict[str, Any]) -> dict[str, Any]:
    content = dict(project.get("content", project))
    summary = dict(content.get("summary", {}))
    answers = dict(content.get("answers", {}))
    scope = dict(answers.get("1_scope", {}))
    execution = dict(answers.get("2_execution", {}))
    capabilities = dict(answers.get("3_capabilities", {}))
    contracts = dict(answers.get("4_contracts_data", {}))
    errors = dict(answers.get("5_errors_state_repro", {}))
    readiness = dict(answers.get("6_runtime_extraction_readiness", {}))
    checks = {
        "has_project_summary": bool(summary.get("root") and summary.get("file_count") is not None),
        "scope_has_task_io_and_areas": _specific_text(scope.get("main_task"))
        and bool(scope.get("inputs"))
        and bool(scope.get("outputs"))
        and isinstance(scope.get("code_areas"), dict),
        "scope_matches_domain_profile": _scope_matches_domain_profile(scope),
        "execution_has_entrypoints_or_controlled_gap": _project_has_execution_anchor(execution, readiness),
        "execution_path_is_pipeline_like": bool(execution.get("primary_execution_path") or execution.get("pipeline_candidate")),
        "capabilities_have_reusable_or_blocked_signal": _project_has_capability_signal(capabilities, readiness),
        "contracts_identify_data_and_weak_zones": bool(contracts.get("main_data_structures"))
        and isinstance(contracts.get("weak_contract_zones", []), list),
        "errors_state_repro_are_explicit": bool(errors.get("likely_error_types"))
        and bool(errors.get("state_to_preserve"))
        and bool(errors.get("minimal_cognitive_loop")),
        "readiness_has_data_lifecycle": _readiness_list_has_rows(readiness.get("data_lifecycle"), "stage"),
        "readiness_has_extraction_plan": _readiness_has_extraction_plan_or_blocked(readiness),
        "evidence_summary_is_source_backed": _project_evidence_summary_is_source_backed(content, readiness),
        "human_summary_is_specific": _project_human_summary_is_specific(content, scope),
        "avoids_generic_phrases": not _has_generic_phrases(content),
    }
    return _result(checks)

def evaluate_architecture_decision(adr: dict[str, Any]) -> dict[str, Any]:
    blocked = _adr_is_blocked_no_candidate(adr)
    checks = {
        "has_decision_summary": _specific_text(adr.get("decision_summary")),
        "chosen_option_has_reason": _specific_text(dict(adr.get("chosen_option", {})).get("reason")),
        "options_show_tradeoffs": _options_have_tradeoffs(adr.get("architecture_options", [])),
        "boundaries_have_io": _boundaries_have_io(adr.get("subsystem_boundaries", [])),
        "data_and_state_models_present": bool(adr.get("data_lifecycle")) and bool(adr.get("state_model")),
        "capabilities_are_source_specific": blocked or _sources_are_specific(adr.get("capability_model", []), "source"),
        "risks_have_mitigation_or_source": _risks_are_actionable(adr.get("risks", [])),
        "traceability_has_targets": blocked or _traceability_is_specific(adr.get("traceability", [])),
        "brief_is_actionable": _brief_is_actionable(adr.get("spec_writer_brief", {}), allow_blocked=blocked),
        "brief_carries_contract_targets": _brief_has_contract_targets(adr.get("spec_writer_brief", {}), allow_blocked=blocked),
        "first_slice_has_evidence_density": blocked or _adr_first_slice_has_evidence_density(adr),
        "architecture_synthesis_is_project_specific": _adr_synthesis_is_project_specific(adr),
        "fact_judgment_ledger_is_explicit": _adr_fact_judgment_ledger_is_explicit(adr),
        "handoff_readiness_has_gates": blocked or _adr_handoff_readiness_has_gates(adr),
        "avoids_generic_phrases": not _has_generic_phrases(adr),
    }
    return _result(checks)

def evaluate_technical_spec(spec: dict[str, Any]) -> dict[str, Any]:
    contract = dict(spec.get("extraction_contract", {}))
    blocked = _contract_is_blocked(contract)
    checks = {
        "requirements_are_specific": _requirements_are_specific(spec.get("requirements", [])),
        "acceptance_is_verifiable": _acceptance_is_verifiable(spec.get("acceptance_criteria", [])),
        "interface_contracts_present": blocked or _interface_contracts_present(spec.get("interface_contracts", []), contract),
        "work_plan_contract_present": _work_plan_contract_present(spec.get("work_plan_contract", {})),
        "data_lifecycle_present": bool(spec.get("data_lifecycle")),
        "error_model_present": _steps_are_actionable(spec.get("error_model", []), "handling"),
        "has_ranked_extraction_contract": blocked or bool(contract.get("candidate") and contract.get("ranked_candidates")),
        "ranked_candidates_have_selection_reasons": blocked or _ranked_candidates_have_selection_reasons(contract),
        "selected_candidate_quality_is_usable": blocked or _selected_candidate_quality_is_usable(contract),
        "contract_has_io": blocked or _contract_has_io(contract),
        "contract_shapes_are_specific": blocked or _contract_shapes_are_specific(contract),
        "side_effects_have_gate": blocked or _contract_side_effects_have_gate(contract),
        "source_evidence_is_specific": blocked or _sources_are_specific(spec.get("source_evidence", []), "source"),
        "selected_candidate_is_source_backed": blocked or _selected_candidate_is_source_backed(contract, spec.get("source_evidence", [])),
        "traceability_links_acceptance": _spec_traceability_links(spec.get("traceability_table", [])),
        "handoff_is_bounded": blocked or _handoff_is_bounded(spec.get("implementation_handoff", {})),
        "engineering_quality_gate_is_explicit": _spec_engineering_quality_gate_is_explicit(spec, blocked=blocked),
        "open_questions_and_non_goals_carried": _spec_open_questions_and_non_goals_carried(spec),
        "avoids_generic_phrases": not _has_generic_phrases(spec),
    }
    return _result(checks)

def evaluate_implementation_plan(plan: dict[str, Any]) -> dict[str, Any]:
    binding = dict(plan.get("contract_binding", {}))
    target = dict(plan.get("implementation_target", {}))
    blocked = _target_is_blocked(target)
    greenfield = _target_is_greenfield(target)
    checks = {
        "target_is_specific": blocked or _looks_like_source(target.get("candidate")) or greenfield,
        "binding_has_contracts": blocked or (isinstance(binding.get("input_contract"), dict) and bool(binding.get("output_contract"))),
        "writable_scope_is_bounded": blocked or _writable_scope_is_bounded(plan) or _greenfield_writable_scope_is_bounded(plan),
        "steps_are_actionable": _steps_are_actionable(plan.get("implementation_steps", []), "action"),
        "verification_commands_present": _commands_are_specific(plan.get("verification_commands", [])),
        "rollback_is_bounded": blocked or _rollback_is_bounded(plan.get("rollback_plan", {})),
        "acceptance_mapping_is_verifiable": _acceptance_mapping_is_verifiable(plan.get("acceptance_mapping", [])),
        "avoids_generic_phrases": not _has_generic_phrases(plan),
    }
    return _result(checks)

def evaluate_test_plan(plan: dict[str, Any]) -> dict[str, Any]:
    target = dict(plan.get("test_target", {}))
    blocked = target.get("binding_status") == "blocked_no_safe_candidate"
    greenfield = _test_target_is_greenfield(target)
    checks = {
        "test_target_is_specific": blocked or _looks_like_source(target.get("candidate")) or greenfield,
        "contract_matrix_is_specific": blocked or _contract_matrix_is_specific(plan.get("contract_test_matrix", [])),
        "strategy_preserves_scope": _strategy_preserves_scope(plan.get("test_strategy", {})),
        "acceptance_tests_are_verifiable": _steps_are_actionable(plan.get("acceptance_tests", []), "criterion"),
        "negative_tests_are_specific": _steps_are_actionable(plan.get("negative_tests", []), "case"),
        "smoke_commands_present": _smoke_commands_present(plan.get("smoke_checklist", [])),
        "regression_risks_have_mitigation": _risks_are_actionable(plan.get("regression_risks", [])),
        "avoids_generic_phrases": not _has_generic_phrases(plan),
    }
    return _result(checks)

def evaluate_review_findings(review: dict[str, Any]) -> dict[str, Any]:
    coverage = dict(review.get("coverage_assessment", {}))
    blocked = dict(review.get("review_target", {})).get("binding_status") == "blocked_no_safe_candidate"
    checks = {
        "review_target_is_specific": blocked or _looks_like_source(dict(review.get("review_target", {})).get("candidate")),
        "coverage_confirms_target": blocked or (coverage.get("target_covered") is True and coverage.get("scope_preserved") is True),
        "findings_are_specific": _steps_are_actionable(review.get("findings", []), "description"),
        "risks_have_mitigation_or_are_low": blocked or _review_risks_are_actionable(review.get("risk_assessment", [])),
        "contract_violations_is_list": isinstance(review.get("contract_violations"), list),
        "architecture_drift_is_list": isinstance(review.get("architecture_drift"), list),
        "recommendation_is_valid": review.get("recommendation") in {"approve", "approve_with_risks", "request_rework"},
        "avoids_generic_phrases": not _has_generic_phrases(review),
    }
    return _result(checks)

def _result(checks: dict[str, bool]) -> dict[str, Any]:
    warnings = [name for name, ok in checks.items() if not ok]
    blocking_warnings = [warning for warning in warnings if _blocking_warning(warning)]
    score = _ratio(sum(1 for ok in checks.values() if ok), len(checks))
    return {
        "passed": score >= 0.9 and not blocking_warnings,
        "score": score,
        "checks": checks,
        "warnings": warnings,
        "blocking_warnings": blocking_warnings,
    }

def _blocking_warning(warning: str) -> bool:
    return warning != "avoids_generic_phrases"

def _specific_text(value: object) -> bool:
    text = str(value or "").strip()
    return len(text) >= 24 and not any(phrase in text.lower() for phrase in GENERIC_PHRASES)

def _sources_are_specific(rows: object, key: str) -> bool:
    if not isinstance(rows, list) or not rows:
        return False
    specific = [row for row in rows if isinstance(row, dict) and _looks_like_source(row.get(key))]
    return len(specific) >= min(2, len(rows))

def _risks_are_actionable(rows: object) -> bool:
    if not isinstance(rows, list) or not rows:
        return False
    return all(
        isinstance(row, dict)
        and _specific_text(row.get("description") or row.get("risk"))
        and bool(row.get("source") or row.get("mitigation"))
        for row in rows[:5]
    )

def _traceability_is_specific(rows: object) -> bool:
    if not isinstance(rows, list) or not rows:
        return False
    return any(isinstance(row, dict) and (row.get("target") or _looks_like_source(row.get("source"))) for row in rows)

def _brief_is_actionable(brief: object, *, allow_blocked: bool = False) -> bool:
    if not isinstance(brief, dict):
        return False
    if allow_blocked:
        return bool(brief.get("blocked_by")) and bool(brief.get("acceptance_targets")) and bool(brief.get("constraints"))
    return bool(brief.get("files_or_symbols")) and bool(brief.get("acceptance_targets")) and bool(brief.get("constraints"))

def _requirements_are_specific(rows: object) -> bool:
    if not isinstance(rows, list) or not rows:
        return False
    return all(isinstance(row, dict) and _specific_text(row.get("statement")) and row.get("priority") for row in rows[:6])

def _acceptance_is_verifiable(rows: object) -> bool:
    if not isinstance(rows, list) or not rows:
        return False
    return all(
        isinstance(row, dict)
        and _specific_text(row.get("criterion"))
        and _specific_text(row.get("verification"))
        for row in rows[:6]
    )

def _steps_are_actionable(rows: object, field: str) -> bool:
    if not isinstance(rows, list) or not rows:
        return False
    return all(isinstance(row, dict) and _specific_text(row.get(field)) for row in rows[:6])

def _commands_are_specific(rows: object) -> bool:
    if not isinstance(rows, list) or not rows:
        return False
    return all(isinstance(item, str) and ("python" in item or "pytest" in item) for item in rows[:4])

def _project_has_execution_anchor(execution: dict[str, Any], readiness: dict[str, Any]) -> bool:
    if execution.get("entrypoints") or execution.get("runtime_commands") or execution.get("central_flow_nodes"):
        return True
    plan = dict(readiness.get("minimal_extraction_plan", {}))
    return bool(plan.get("capabilities_to_extract")) or _plan_blocks_no_safe_python_candidate(plan)

def _project_has_capability_signal(capabilities: dict[str, Any], readiness: dict[str, Any]) -> bool:
    if capabilities.get("atomic_reusable_capabilities") or capabilities.get("pure_transforms") or capabilities.get("too_broad_functions"):
        return True
    plan = dict(readiness.get("minimal_extraction_plan", {}))
    return bool(plan.get("capabilities_to_extract")) or _plan_blocks_no_safe_python_candidate(plan)

def _readiness_list_has_rows(rows: object, key: str) -> bool:
    return isinstance(rows, list) and bool(rows) and all(isinstance(row, dict) and row.get(key) for row in rows[:4])

def _readiness_has_extraction_plan_or_blocked(readiness: dict[str, Any]) -> bool:
    plan = dict(readiness.get("minimal_extraction_plan", {}))
    return bool(plan.get("capabilities_to_extract")) or _plan_blocks_no_safe_python_candidate(plan)

def _project_evidence_summary_is_source_backed(content: dict[str, Any], readiness: dict[str, Any]) -> bool:
    summary = dict(content.get("evidence_summary") or {})
    if summary:
        sources = summary.get("source_refs")
        limits = summary.get("limits")
        confidence = summary.get("confidence")
        return isinstance(sources, list) and bool(sources) and isinstance(limits, list) and confidence is not None
    evidence_refs: list[str] = []
    for key in ("data_lifecycle", "hidden_orchestrators", "process_boundary_candidates", "quarantine_candidates"):
        for row in list(readiness.get(key, []) or [])[:5]:
            if isinstance(row, dict):
                ref = row.get("evidence") or row.get("target") or row.get("source")
                if ref:
                    evidence_refs.append(str(ref))
    return len(evidence_refs) >= 2

def _project_human_summary_is_specific(content: dict[str, Any], scope: dict[str, Any]) -> bool:
    human = dict(content.get("human_summary") or {})
    if human:
        return _specific_text(human.get("purpose")) and bool(human.get("main_scenarios")) and bool(human.get("recommended_next_step"))
    return _specific_text(scope.get("main_task")) and bool(scope.get("supported_scenarios") or scope.get("inputs"))

def _plan_blocks_no_safe_python_candidate(plan: dict[str, Any]) -> bool:
    return "no_safe_python_candidate" in [str(item) for item in list(plan.get("blocked_by", []) or [])]

def _scope_matches_domain_profile(scope: dict[str, Any]) -> bool:
    profile = dict(scope.get("domain_profile") or {})
    kind = str(profile.get("kind") or "")
    if not kind or kind == "generic":
        return True
    task = str(scope.get("main_task") or "").lower()
    purpose = str(profile.get("purpose_summary") or "").lower()
    if purpose:
        return _token_overlap(task, purpose) >= 0.35
    expected = {
        "llm_provider_gateway": ["gateway", "provider", "chat", "completion"],
        "llm_auto_repair_loop": ["repair", "docker", "template", "retry"],
        "ml_competition_inference_script": ["csv", "model", "submission", "inference"],
        "prompt_lab_evaluation_runtime": ["prompt", "laboratory", "validation", "enrichment", "experiment"],
        "prompt_to_code_compiler_pipeline": ["spec", "compile", "graph", "artifact"],
        "multi_agent_orchestration_runtime": ["agent", "orchestration", "consensus", "a2a"],
    }.get(kind, [])
    if not expected:
        return True
    return sum(1 for token in expected if token in task) >= max(1, min(2, len(expected)))

def _token_overlap(left: str, right: str) -> float:
    left_tokens = {token for token in _simple_tokens(left) if len(token) >= 4}
    right_tokens = {token for token in _simple_tokens(right) if len(token) >= 4}
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / max(1, len(right_tokens))

def _simple_tokens(text: str) -> list[str]:
    return [chunk.strip(".,;:()[]{}<>/\\\"'`").lower() for chunk in text.split()]

def _options_have_tradeoffs(rows: object) -> bool:
    if not isinstance(rows, list) or len(rows) < 2:
        return False
    return all(isinstance(row, dict) and row.get("id") and row.get("tradeoffs") for row in rows[:3])
