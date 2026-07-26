"""Deterministic wording-quality checks for L4 role artifacts."""

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
    score = _ratio(sum(float(item["score"]) for item in results.values()), len(results))
    return {
        "passed": score >= 0.9 and not warnings,
        "score": score,
        "results": results,
        "warnings": warnings,
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
        "avoids_generic_phrases": not _has_generic_phrases(adr),
    }
    return _result(checks)


def evaluate_technical_spec(spec: dict[str, Any]) -> dict[str, Any]:
    contract = dict(spec.get("extraction_contract", {}))
    blocked = _contract_is_blocked(contract)
    checks = {
        "requirements_are_specific": _requirements_are_specific(spec.get("requirements", [])),
        "acceptance_is_verifiable": _acceptance_is_verifiable(spec.get("acceptance_criteria", [])),
        "interface_contracts_present": blocked or _interface_contracts_present(spec.get("interface_contracts", [])),
        "work_plan_contract_present": _work_plan_contract_present(spec.get("work_plan_contract", {})),
        "data_lifecycle_present": bool(spec.get("data_lifecycle")),
        "error_model_present": _steps_are_actionable(spec.get("error_model", []), "handling"),
        "has_ranked_extraction_contract": blocked or bool(contract.get("candidate") and contract.get("ranked_candidates")),
        "ranked_candidates_have_selection_reasons": blocked or _ranked_candidates_have_selection_reasons(contract),
        "selected_candidate_quality_is_usable": blocked or _selected_candidate_quality_is_usable(contract),
        "contract_has_io": blocked or bool(contract.get("input_contract") and contract.get("output_contract")),
        "contract_shapes_are_specific": blocked or _contract_shapes_are_specific(contract),
        "side_effects_have_gate": blocked or _contract_side_effects_have_gate(contract),
        "source_evidence_is_specific": blocked or _sources_are_specific(spec.get("source_evidence", []), "source"),
        "selected_candidate_is_source_backed": blocked or _selected_candidate_is_source_backed(contract, spec.get("source_evidence", [])),
        "traceability_links_acceptance": _spec_traceability_links(spec.get("traceability_table", [])),
        "handoff_is_bounded": blocked or _handoff_is_bounded(spec.get("implementation_handoff", {})),
        "avoids_generic_phrases": not _has_generic_phrases(spec),
    }
    return _result(checks)


def evaluate_implementation_plan(plan: dict[str, Any]) -> dict[str, Any]:
    binding = dict(plan.get("contract_binding", {}))
    target = dict(plan.get("implementation_target", {}))
    blocked = _target_is_blocked(target)
    checks = {
        "target_is_specific": blocked or _looks_like_source(target.get("candidate")),
        "binding_has_contracts": blocked or bool(binding.get("input_contract") and binding.get("output_contract")),
        "writable_scope_is_bounded": blocked or _writable_scope_is_bounded(plan),
        "steps_are_actionable": _steps_are_actionable(plan.get("implementation_steps", []), "action"),
        "verification_commands_present": _commands_are_specific(plan.get("verification_commands", [])),
        "rollback_is_bounded": blocked or _rollback_is_bounded(plan.get("rollback_plan", {})),
        "acceptance_mapping_is_verifiable": _acceptance_mapping_is_verifiable(plan.get("acceptance_mapping", [])),
        "avoids_generic_phrases": not _has_generic_phrases(plan),
    }
    return _result(checks)


def evaluate_test_plan(plan: dict[str, Any]) -> dict[str, Any]:
    blocked = dict(plan.get("test_target", {})).get("binding_status") == "blocked_no_safe_candidate"
    checks = {
        "test_target_is_specific": blocked or _looks_like_source(dict(plan.get("test_target", {})).get("candidate")),
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
    return {"passed": not warnings, "score": _ratio(sum(1 for ok in checks.values() if ok), len(checks)), "checks": checks, "warnings": warnings}


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


def _boundaries_have_io(rows: object) -> bool:
    if not isinstance(rows, list) or not rows:
        return False
    return all(isinstance(row, dict) and row.get("owned_files") and row.get("inputs") and row.get("outputs") for row in rows[:4])


def _brief_has_contract_targets(brief: object, *, allow_blocked: bool = False) -> bool:
    if not isinstance(brief, dict):
        return False
    if allow_blocked:
        return bool(brief.get("blocked_by"))
    return bool(brief.get("contract_targets") or brief.get("data_contract_targets"))


def _adr_first_slice_has_evidence_density(adr: dict[str, Any]) -> bool:
    first_slice = dict(adr.get("first_slice_contract", {}))
    targets = [str(item) for item in list(first_slice.get("targets", [])) if _looks_like_source(item)]
    if not targets:
        return False
    context = dict(adr.get("source_context", {}))
    traceability = list(adr.get("traceability", []) or [])
    capability_sources = [str(row.get("source") or "") for row in list(adr.get("capability_model", []) or []) if isinstance(row, dict)]
    evidence_refs = set(context) | set(capability_sources)
    for row in traceability:
        if isinstance(row, dict):
            evidence_refs.add(str(row.get("source") or ""))
            evidence_refs.add(str(row.get("target") or ""))
    matched = sum(1 for target in targets[:4] if _source_ref_matches_any(target, evidence_refs))
    return matched >= 1 and len(evidence_refs) >= 3


def _adr_synthesis_is_project_specific(adr: dict[str, Any]) -> bool:
    if _adr_is_blocked_no_candidate(adr):
        return True
    synthesis = dict(adr.get("architecture_synthesis", {}))
    profile = dict(synthesis.get("project_profile", {}))
    first_slice = dict(adr.get("first_slice_contract", {}))
    if not profile.get("archetype") or str(profile.get("archetype")) == "generic":
        return False
    return bool(first_slice.get("name") and first_slice.get("targets"))


def _interface_contracts_present(rows: object) -> bool:
    if not isinstance(rows, list) or not rows:
        return False
    for row in rows[:6]:
        if not isinstance(row, dict):
            return False
        if not row.get("source") or not row.get("input_contract") or not row.get("output_contract"):
            return False
    return True


def _work_plan_contract_present(value: object) -> bool:
    if not isinstance(value, dict):
        return False
    if value.get("status") == "blocked_no_first_slice":
        return bool(value.get("blocked_by"))
    obligations = value.get("obligations", [])
    return (
        _specific_text(value.get("goal"))
        and isinstance(obligations, list)
        and bool(obligations)
        and all(isinstance(row, dict) and row.get("id") and _specific_text(row.get("step")) for row in obligations[:4])
    )


def _writable_scope_is_bounded(plan: dict[str, Any]) -> bool:
    target = str(dict(plan.get("implementation_target", {})).get("candidate") or "")
    writable = [str(item) for item in plan.get("writable_scope", []) if item]
    return bool(target and writable == [target])


def _rollback_is_bounded(rollback: object) -> bool:
    if not isinstance(rollback, dict):
        return False
    return _specific_text(rollback.get("strategy")) and bool(rollback.get("files")) and "registry" in str(rollback.get("registry_policy", "")).lower()


def _acceptance_mapping_is_verifiable(rows: object) -> bool:
    if not isinstance(rows, list) or not rows:
        return False
    return all(isinstance(row, dict) and row.get("acceptance_id") and _specific_text(row.get("criterion")) for row in rows[:6])


def _contract_matrix_is_specific(rows: object) -> bool:
    if not isinstance(rows, list) or not rows:
        return False
    return all(isinstance(row, dict) and row.get("target") and row.get("direction") in {"input", "output"} and row.get("field") for row in rows[:6])


def _strategy_preserves_scope(strategy: object) -> bool:
    if not isinstance(strategy, dict):
        return False
    return bool(strategy.get("writable_scope")) and isinstance(strategy.get("read_only_context", []), list) and _specific_text(strategy.get("principle"))


def _smoke_commands_present(rows: object) -> bool:
    if not isinstance(rows, list) or not rows:
        return False
    return all(isinstance(row, dict) and _command_text_is_specific(row.get("command")) for row in rows[:4])


def _command_text_is_specific(value: object) -> bool:
    text = str(value or "").strip()
    return bool(text and ("python" in text or "pytest" in text or "compileall" in text))


def _review_risks_are_actionable(rows: object) -> bool:
    if not isinstance(rows, list) or not rows:
        return False
    for row in rows[:6]:
        if not isinstance(row, dict) or not _specific_text(row.get("risk")):
            return False
        if row.get("severity") != "low" and not _specific_text(row.get("mitigation")):
            return False
    return True


def _spec_traceability_links(rows: object) -> bool:
    if not isinstance(rows, list) or not rows:
        return False
    return all(isinstance(row, dict) and row.get("source") and row.get("acceptance_id") for row in rows[:6])


def _handoff_is_bounded(handoff: object) -> bool:
    if not isinstance(handoff, dict):
        return False
    return handoff.get("recommended_role") == "implementer" and bool(handoff.get("patch_scope"))


def _adr_is_blocked_no_candidate(adr: dict[str, Any]) -> bool:
    return "no_safe_source_specific_candidate" in list(dict(adr.get("spec_writer_brief", {})).get("blocked_by", []))


def _contract_is_blocked(contract: dict[str, Any]) -> bool:
    return contract.get("status") == "blocked_no_safe_candidate"


def _contract_shapes_are_specific(contract: dict[str, Any]) -> bool:
    if contract.get("contract_family"):
        return True
    values = list(dict(contract.get("input_contract", {})).values()) + list(dict(contract.get("output_contract", {})).values())
    if not values:
        return False
    return all(str(value).strip().lower() not in {"", "any", "none"} for value in values)


def _contract_side_effects_have_gate(contract: dict[str, Any]) -> bool:
    side_effects = dict(contract.get("side_effects", {}))
    declared = list(side_effects.get("declared", []) or [])
    if not declared:
        return True
    return bool(
        side_effects.get("requires_validation_gate")
        or side_effects.get("requires_process_boundary")
        or side_effects.get("idempotency_required")
        or side_effects.get("retry_policy")
    )


def _ranked_candidates_have_selection_reasons(contract: dict[str, Any]) -> bool:
    rows = list(contract.get("ranked_candidates", []) or [])
    if not rows:
        return False
    for row in rows[: min(3, len(rows))]:
        if not isinstance(row, dict) or not row.get("source") or not row.get("reasons"):
            return False
    return True


def _selected_candidate_quality_is_usable(contract: dict[str, Any]) -> bool:
    quality = dict(contract.get("semantic_quality", {}) or {})
    status = str(quality.get("status") or "")
    if status in {"strong", "acceptable"}:
        return True
    return bool(contract.get("contract_family") and status != "poor")


def _selected_candidate_is_source_backed(contract: dict[str, Any], evidence: object) -> bool:
    candidate = str(contract.get("candidate") or "")
    if not candidate:
        return False
    evidence_refs = {
        str(row.get("source") or "")
        for row in list(evidence or [])
        if isinstance(row, dict) and row.get("source")
    }
    ranked_refs = {
        str(row.get("source") or "")
        for row in list(contract.get("ranked_candidates", []) or [])
        if isinstance(row, dict) and row.get("source")
    }
    return _source_ref_matches_any(candidate, evidence_refs | ranked_refs)


def _source_ref_matches_any(source: str, refs: set[str]) -> bool:
    clean = _normalize_source_ref(source)
    return any(clean == _normalize_source_ref(ref) for ref in refs if ref)


def _normalize_source_ref(value: object) -> str:
    text = str(value or "").strip()
    if "(" in text and text.endswith(")"):
        text = text.rsplit("(", 1)[0].strip()
    return text.replace("\\", "/")


def _target_is_blocked(target: dict[str, Any]) -> bool:
    return target.get("status") == "blocked_no_safe_candidate"


def _looks_like_source(value: object) -> bool:
    text = str(value or "")
    return bool(text and (":" in text or "/" in text or "\\" in text or text.endswith(".py")))


def _has_generic_phrases(value: object) -> bool:
    text = _flatten_text(value).lower()
    return any(phrase in text for phrase in GENERIC_PHRASES)


def _flatten_text(value: object) -> str:
    if isinstance(value, dict):
        return " ".join(_flatten_text(item) for item in value.values())
    if isinstance(value, list):
        return " ".join(_flatten_text(item) for item in value)
    return str(value or "")


def _ratio(numerator: float, denominator: float) -> float:
    return 1.0 if denominator == 0 else round(numerator / denominator, 4)
