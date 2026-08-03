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

def _adr_fact_judgment_ledger_is_explicit(adr: dict[str, Any]) -> bool:
    ledger = dict(adr.get("fact_judgment_ledger") or {})
    facts = list(ledger.get("facts") or [])
    judgments = list(ledger.get("judgments") or [])
    if not facts or not judgments:
        return False
    fact_ok = all(isinstance(row, dict) and row.get("claim") and row.get("evidence_source") for row in facts[:6])
    judgment_ok = all(
        isinstance(row, dict)
        and row.get("judgment")
        and row.get("based_on")
        and row.get("confidence") is not None
        and row.get("validation_gate")
        for row in judgments[:6]
    )
    return fact_ok and judgment_ok

def _adr_handoff_readiness_has_gates(adr: dict[str, Any]) -> bool:
    gate = dict(adr.get("spec_writer_handoff_readiness") or {})
    checks = dict(gate.get("checks") or {})
    return gate.get("status") in {"ready", "blocked"} and bool(checks) and all(value is True for value in checks.values())

def _interface_contracts_present(rows: object, selected_contract: dict[str, Any] | None = None) -> bool:
    if not isinstance(rows, list) or not rows:
        return False
    for row in rows[:6]:
        if not isinstance(row, dict):
            return False
        input_contract = row.get("input_contract")
        input_ok = bool(input_contract) or isinstance(input_contract, dict)
        if not row.get("source") or not input_ok or not row.get("output_contract"):
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

def _target_is_greenfield(target: dict[str, Any]) -> bool:
    candidate = str(target.get("candidate") or "")
    return candidate.startswith("greenfield:") and target.get("mode") == "greenfield_project"

def _test_target_is_greenfield(target: dict[str, Any]) -> bool:
    candidate = str(target.get("candidate") or "")
    return candidate.startswith("greenfield:") and target.get("binding_status") == "bound_to_product_contract"

def _greenfield_writable_scope_is_bounded(plan: dict[str, Any]) -> bool:
    target = dict(plan.get("implementation_target", {}))
    if not _target_is_greenfield(target):
        return False
    expected = [str(item) for item in plan.get("expected_files", []) if item]
    writable = [str(item) for item in plan.get("writable_scope", []) if item]
    return bool(expected and writable and set(writable).issubset(set(expected)))

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

def _spec_engineering_quality_gate_is_explicit(spec: dict[str, Any], *, blocked: bool) -> bool:
    gate = dict(spec.get("engineering_quality_gate") or {})
    if not gate:
        return False
    checks = dict(gate.get("checks") or {})
    required = {
        "source_evidence_bound",
        "io_contract_bound",
        "negative_acceptance_present",
        "handoff_scope_bound",
    }
    if blocked:
        return gate.get("status") == "blocked" and bool(gate.get("blocked_by"))
    return gate.get("status") == "ready" and required.issubset(checks) and all(checks.get(key) is True for key in required)

def _spec_open_questions_and_non_goals_carried(spec: dict[str, Any]) -> bool:
    return isinstance(spec.get("open_questions"), list) and isinstance(spec.get("non_goals"), list) and bool(spec.get("non_goals"))

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

def _contract_has_io(contract: dict[str, Any]) -> bool:
    return isinstance(contract.get("input_contract"), dict) and bool(contract.get("output_contract"))

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
    review = dict(contract.get("semantic_review") or {})
    checks = dict(review.get("checks") or {})
    if review.get("status") == "approved_with_constraints" and checks and all(checks.values()):
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
    text = _flatten_quality_text(value).lower()
    return any(phrase in text for phrase in GENERIC_PHRASES)

def _flatten_quality_text(value: object, *, key_path: tuple[str, ...] = ()) -> str:
    if _source_text_key_path(key_path):
        return ""
    if isinstance(value, dict):
        return " ".join(_flatten_quality_text(item, key_path=(*key_path, str(key))) for key, item in value.items())
    if isinstance(value, list):
        return " ".join(_flatten_quality_text(item, key_path=key_path) for item in value)
    return str(value or "")

def _source_text_key_path(key_path: tuple[str, ...]) -> bool:
    lowered = tuple(item.lower() for item in key_path)
    if "source_context" in lowered:
        return True
    if "source_evidence" in lowered:
        return any(item in {"snippet", "text"} for item in lowered)
    return False

def _flatten_text(value: object) -> str:
    if isinstance(value, dict):
        return " ".join(_flatten_text(item) for item in value.values())
    if isinstance(value, list):
        return " ".join(_flatten_text(item) for item in value)
    return str(value or "")

def _ratio(numerator: float, denominator: float) -> float:
    return 1.0 if denominator == 0 else round(numerator / denominator, 4)
