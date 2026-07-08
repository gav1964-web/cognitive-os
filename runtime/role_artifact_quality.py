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
    adr = dict(artifacts.get("architecture_decision", {}))
    spec = dict(artifacts.get("technical_spec", {}))
    results = {
        "adr": evaluate_architecture_decision(adr),
        "technical_spec": evaluate_technical_spec(spec),
    }
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


def evaluate_architecture_decision(adr: dict[str, Any]) -> dict[str, Any]:
    blocked = _adr_is_blocked_no_candidate(adr)
    checks = {
        "has_decision_summary": _specific_text(adr.get("decision_summary")),
        "chosen_option_has_reason": _specific_text(dict(adr.get("chosen_option", {})).get("reason")),
        "capabilities_are_source_specific": blocked or _sources_are_specific(adr.get("capability_model", []), "source"),
        "risks_have_mitigation_or_source": _risks_are_actionable(adr.get("risks", [])),
        "traceability_has_targets": blocked or _traceability_is_specific(adr.get("traceability", [])),
        "brief_is_actionable": _brief_is_actionable(adr.get("spec_writer_brief", {}), allow_blocked=blocked),
        "avoids_generic_phrases": not _has_generic_phrases(adr),
    }
    return _result(checks)


def evaluate_technical_spec(spec: dict[str, Any]) -> dict[str, Any]:
    contract = dict(spec.get("extraction_contract", {}))
    blocked = _contract_is_blocked(contract)
    checks = {
        "requirements_are_specific": _requirements_are_specific(spec.get("requirements", [])),
        "acceptance_is_verifiable": _acceptance_is_verifiable(spec.get("acceptance_criteria", [])),
        "has_ranked_extraction_contract": blocked or bool(contract.get("candidate") and contract.get("ranked_candidates")),
        "contract_has_io": blocked or bool(contract.get("input_contract") and contract.get("output_contract")),
        "source_evidence_is_specific": blocked or _sources_are_specific(spec.get("source_evidence", []), "source"),
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
