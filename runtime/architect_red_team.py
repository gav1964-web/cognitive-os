"""Red-team checks for ArchitectureDecisionRecord before SpecWriter handoff."""

from __future__ import annotations

from typing import Any

from runtime.scope_selection_policy import syntax_error_fixture_path


def red_team_architecture_decision(adr: dict[str, Any], project_report: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return an explicit verdict for ADR -> SpecWriter handoff."""

    project_report = project_report or {}
    chosen = dict(adr.get("chosen_option", {}))
    first_slice = dict(adr.get("first_slice_contract", {}))
    brief = dict(adr.get("spec_writer_brief", {}))
    findings: list[dict[str, Any]] = []

    blocked = _blocked_no_candidate(adr)
    _require(findings, bool(chosen.get("id") and chosen.get("reason")), "missing_chosen_option", "ADR must choose one architecture option with reason.")
    _require(
        findings,
        _options_have_tradeoffs(adr.get("architecture_options", [])),
        "missing_option_tradeoffs",
        "ADR must expose tradeoffs, not a single unchallenged recommendation.",
    )
    _require(
        findings,
        _rejected_options_are_explained(adr.get("rejected_options", [])),
        "rejected_options_not_explained",
        "Rejected options must carry score delta, tradeoffs, deferred-until condition, and reason.",
    )
    _require(
        findings,
        blocked or _first_slice_is_bounded(first_slice),
        "first_slice_not_bounded",
        "First slice must have a name, goal, source-backed targets, and concrete steps.",
    )
    _require(
        findings,
        blocked or bool(first_slice.get("selection_policy") and first_slice.get("handoff_expectation")),
        "first_slice_policy_missing",
        "First slice must explain why this slice is first and how SpecWriter may use it.",
    )
    _require(
        findings,
        blocked or _brief_is_bounded(brief),
        "spec_writer_brief_not_bounded",
        "SpecWriter brief must include files/symbols, constraints, acceptance targets, and contract targets.",
    )
    _require(
        findings,
        blocked or _brief_sources_have_context(brief, dict(adr.get("source_context", {}))),
        "brief_sources_without_context",
        "SpecWriter brief sources must have source_context evidence or be explicit ProjectMapReport references.",
    )
    _require(
        findings,
        blocked or _traceability_links_targets(adr.get("traceability", [])),
        "traceability_not_source_linked",
        "ADR traceability must point to source targets or first-slice targets.",
    )
    _require(
        findings,
        _risks_are_actionable(adr.get("risks", [])),
        "risks_not_actionable",
        "ADR risks must include severity, impact, mitigation, and evidence source.",
    )
    _require(
        findings,
        _forbidden_actions_enforced(adr),
        "forbidden_actions_not_enforced",
        "ADR must explicitly enforce no code write, registry edit, pipeline execution, or promote.",
    )
    _require(
        findings,
        isinstance(adr.get("open_questions", []), list),
        "open_questions_not_structured",
        "ADR must carry open questions as a structured list, even when empty.",
        severity="medium",
    )
    _require(
        findings,
        _project_context_matches(adr, project_report),
        "project_context_missing",
        "ADR should preserve project identity from ProjectMapReport.",
        severity="medium",
    )
    _require(
        findings,
        _source_tree_scope_is_clean(project_report),
        "source_tree_requires_scope_decision",
        "Dirty or snapshot-mixed source trees require an explicit active-root/scope decision before ADR can pass foundation gates.",
    )
    _require(
        findings,
        _source_tree_noise_is_acknowledged(project_report),
        "source_tree_has_noise_artifacts",
        "Noisy source trees should record cleanup/exclusion evidence for .env, logs, archives, caches, and generated artifacts.",
        severity="medium",
    )

    blocking = [row for row in findings if row["severity"] == "high"]
    warnings = [row for row in findings if row["severity"] != "high"]
    return {
        "artifact_type": "ArchitectRedTeamReport",
        "status": "pass" if not blocking else "fail",
        "handoff_verdict": "ready_for_spec_writer" if not blocking else "return_to_architect",
        "blocking_findings": blocking,
        "warnings": warnings,
        "score": round(max(0.0, 1.0 - len(blocking) * 0.18 - len(warnings) * 0.06), 4),
        "checked_option": chosen.get("id"),
        "checked_first_slice": first_slice.get("name"),
    }


def _require(
    findings: list[dict[str, Any]],
    condition: bool,
    code: str,
    message: str,
    *,
    severity: str = "high",
) -> None:
    if not condition:
        findings.append({"severity": severity, "code": code, "message": message})


def _blocked_no_candidate(adr: dict[str, Any]) -> bool:
    brief = dict(adr.get("spec_writer_brief", {}))
    return "no_safe_source_specific_candidate" in list(brief.get("blocked_by", []))


def _options_have_tradeoffs(rows: object) -> bool:
    if not isinstance(rows, list) or len(rows) < 2:
        return False
    return all(isinstance(row, dict) and row.get("id") and row.get("tradeoffs") for row in rows[:3])


def _rejected_options_are_explained(rows: object) -> bool:
    if not isinstance(rows, list) or not rows:
        return False
    return all(
        isinstance(row, dict)
        and row.get("id")
        and row.get("reason_rejected")
        and row.get("tradeoffs")
        and row.get("deferred_until")
        and row.get("score_delta") is not None
        for row in rows[:3]
    )


def _first_slice_is_bounded(first_slice: dict[str, Any]) -> bool:
    targets = [str(item) for item in list(first_slice.get("targets", [])) if item]
    steps = [str(item) for item in list(first_slice.get("steps", [])) if item]
    return bool(first_slice.get("name") and first_slice.get("goal") and steps) and any(_looks_like_source(target) for target in targets)


def _risks_are_actionable(rows: object) -> bool:
    if not isinstance(rows, list) or not rows:
        return False
    return all(
        isinstance(row, dict)
        and row.get("severity")
        and row.get("description")
        and row.get("impact")
        and row.get("mitigation")
        and row.get("evidence_source")
        for row in rows[:5]
    )


def _brief_is_bounded(brief: dict[str, Any]) -> bool:
    sources = list(brief.get("files_or_symbols", []) or [])
    contract_targets = list(brief.get("contract_targets", []) or [])
    return bool(sources and brief.get("acceptance_targets") and brief.get("constraints") and contract_targets)


def _brief_sources_have_context(brief: dict[str, Any], source_context: dict[str, Any]) -> bool:
    contract_sources = [
        _normalize_source_ref(str(row.get("source")))
        for row in list(brief.get("contract_targets", []))
        if isinstance(row, dict)
        and _looks_like_source(row.get("source"))
        and not _looks_like_contract_type_ref(str(row.get("source")))
        and _contract_target_has_derived_context(row)
    ]
    supporting_sources = [
        _normalize_source_ref(str(item))
        for item in list(brief.get("files_or_symbols", []))
        if _looks_like_source(item) and not _looks_like_contract_type_ref(str(item))
    ]
    sources = list(dict.fromkeys(contract_sources or supporting_sources))
    if not sources:
        return False
    checked = sources[:8]
    present = 0
    normalized_context = {_normalize_source_ref(str(key)) for key in source_context}
    for source in checked:
        if source.startswith("ProjectMapReport."):
            present += 1
        elif source in source_context or source in normalized_context:
            present += 1
    if contract_sources:
        return present == len(checked)
    return present >= max(1, min(3, len(checked)))


def _traceability_links_targets(rows: object) -> bool:
    if not isinstance(rows, list) or not rows:
        return False
    for row in rows:
        if not isinstance(row, dict):
            continue
        if _looks_like_source(row.get("source")) or _looks_like_source(row.get("target")):
            return True
    return False


def _forbidden_actions_enforced(adr: dict[str, Any]) -> bool:
    enforced = {str(item) for item in list(adr.get("forbidden_actions_enforced", []))}
    return {"write_code", "edit_registry", "execute_pipeline", "promote_candidate"}.issubset(enforced)


def _project_context_matches(adr: dict[str, Any], project_report: dict[str, Any]) -> bool:
    if not project_report:
        return bool(adr.get("project"))
    return bool(adr.get("project") or project_report.get("project") or dict(project_report.get("summary", {})).get("root"))


def _source_tree_scope_is_clean(project_report: dict[str, Any]) -> bool:
    if not project_report:
        return True
    source_health = _source_health(project_report)
    if not source_health:
        return True
    status = str(source_health.get("status") or "clean")
    shape = str(source_health.get("project_shape") or "single_project")
    if _syntax_damage_is_fixture_only(source_health):
        return True
    if status == "damaged" or shape == "dirty_portfolio" or int(source_health.get("packaged_copy_signal_count") or 0) > 0:
        return bool(source_health.get("active_root_decision"))
    return True


def _source_tree_noise_is_acknowledged(project_report: dict[str, Any]) -> bool:
    if not project_report:
        return True
    source_health = _source_health(project_report)
    if not source_health:
        return True
    noisy_count = (
        int(source_health.get("artifact_noise_signal_count") or 0)
        + int(source_health.get("env_file_signal_count") or 0)
        + int(source_health.get("generated_run_signal_count") or 0)
    )
    if noisy_count == 0:
        return True
    return bool(source_health.get("noise_exclusion_decision"))


def _source_health(project_report: dict[str, Any]) -> dict[str, Any]:
    content = dict(project_report.get("content", project_report))
    return dict(content.get("source_health") or dict(content.get("answers", {})).get("0_source_health") or {})


def _syntax_damage_is_fixture_only(source_health: dict[str, Any]) -> bool:
    if source_health.get("status") != "damaged" or int(source_health.get("inaccessible_count") or 0) > 0:
        return False
    count = int(source_health.get("syntax_error_count") or 0)
    samples = [dict(row) for row in list(source_health.get("syntax_error_samples") or []) if isinstance(row, dict)]
    if not count or count > len(samples):
        return False
    return all(syntax_error_fixture_path(str(row.get("path") or "")) for row in samples)


def _looks_like_source(value: object) -> bool:
    text = str(value or "")
    return bool(text and (".py:" in text or ":" in text or text.startswith("ProjectMapReport.")))


def _normalize_source_ref(source: str) -> str:
    return source.split("(", 1)[0].strip() if source.lower().rstrip().endswith("loc)") else source.strip()


def _looks_like_contract_type_ref(source: str) -> bool:
    symbol = _normalize_source_ref(source).rsplit(":", 1)[-1]
    if not symbol:
        return False
    return symbol.endswith(("Error", "Exception", "Failure", "Packet", "Request", "Response", "Result")) or symbol[:1].isupper()


def _contract_target_has_derived_context(row: dict[str, Any]) -> bool:
    text = f"{row.get('input_hint', '')} {row.get('output_hint', '')}".lower()
    return "derive from source" not in text
