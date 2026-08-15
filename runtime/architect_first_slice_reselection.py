"""Architect-owned expansion of a rejected first-slice candidate window."""

from __future__ import annotations

from typing import Any

from .role_source_context import build_source_context
from .spec_writer_target_binding import standalone_target_eligibility
from .technical_spec_policy import load_technical_spec_policy


def reselect_architecture_first_slice(
    *,
    architecture_decision: dict[str, Any],
    technical_spec: dict[str, Any],
    project_report: dict[str, Any],
    iteration: int,
) -> dict[str, Any]:
    request = dict(technical_spec.get("first_slice_reselection_request") or {})
    if request.get("status") != "required":
        return {"status": "not_required", "architecture_decision": architecture_decision}
    policy = dict(load_technical_spec_policy().get("first_slice_reselection") or {})
    sources = _expanded_candidate_sources(project_report, architecture_decision, policy)
    project_root = str(
        architecture_decision.get("project")
        or dict(project_report.get("summary") or {}).get("root")
        or project_report.get("root")
        or ""
    )
    expanded_context = build_source_context(
        project_root=project_root,
        project_report=project_report,
        sources=sources,
    )
    ready = [source for source in sources if _environment_ready_callable(expanded_context.get(source))]
    selected = ready[: max(1, int(policy.get("selected_target_limit") or 8))]
    evidence = {
        "artifact_type": "FirstSliceReselectionOutcome",
        "iteration": iteration,
        "status": "selected" if selected else "exhausted",
        "trigger": request.get("trigger"),
        "expanded_candidate_count": len(sources),
        "environment_ready_candidate_count": len(ready),
        "selected_targets": selected,
        "authority": "architect",
        "source": "ProjectMapReport expanded candidate evidence",
    }
    if not selected:
        return {
            "status": "exhausted",
            "architecture_decision": _attach_outcome(architecture_decision, evidence),
            "outcome": evidence,
        }
    revised = _revised_architecture_decision(
        architecture_decision,
        expanded_context=expanded_context,
        selected_targets=selected,
        outcome=evidence,
    )
    return {"status": "selected", "architecture_decision": revised, "outcome": evidence}


def _expanded_candidate_sources(
    project_report: dict[str, Any],
    architecture_decision: dict[str, Any],
    policy: dict[str, Any],
) -> list[str]:
    answers = dict(project_report.get("answers") or {})
    capabilities = dict(answers.get("3_capabilities") or {})
    readiness = dict(answers.get("6_runtime_extraction_readiness") or {})
    plan = dict(readiness.get("minimal_extraction_plan") or {})
    enabled = {str(item) for item in list(policy.get("candidate_sources") or [])}
    sources: list[str] = []
    for key in ("pure_transforms", "atomic_reusable_capabilities", "too_broad_functions"):
        if key in enabled:
            sources.extend(_row_sources(capabilities.get(key)))
    for key in ("process_boundary_candidates", "mixed_responsibility_functions", "hidden_orchestrators"):
        if key in enabled:
            sources.extend(_row_sources(readiness.get(key)))
    if "dataflows" in enabled:
        sources.extend(str(row.get("entrypoint") or "") for row in _rows(readiness.get("dataflows")))
    if "minimal_extraction_plan" in enabled:
        sources.extend(_row_sources(plan.get("capabilities_to_extract")))
    sources.extend(str(item) for item in dict(architecture_decision.get("source_context") or {}))
    limit = max(1, int(policy.get("expanded_candidate_limit") or 64))
    return list(dict.fromkeys(source for source in sources if ".py:" in source))[:limit]


def _row_sources(value: Any) -> list[str]:
    sources = []
    for row in _rows(value):
        source = row.get("source") or row.get("target") or row.get("capability")
        if not source and row.get("path") and row.get("name"):
            source = f"{row['path']}:{row['name']}"
        if source:
            sources.append(str(source))
    return sources


def _rows(value: Any) -> list[dict[str, Any]]:
    return [dict(row) for row in list(value or []) if isinstance(row, dict)]


def _environment_ready_callable(context: dict[str, Any] | None) -> bool:
    row = dict(context or {})
    snippet = dict(row.get("snippet") or {})
    readiness = dict(row.get("dependency_readiness") or {})
    eligibility = standalone_target_eligibility({"target_binding": snippet.get("target_binding")})
    return bool(
        row.get("node_kind") == "function"
        and snippet.get("text")
        and readiness.get("status") == "ready"
        and eligibility.get("eligible")
    )


def _revised_architecture_decision(
    architecture_decision: dict[str, Any],
    *,
    expanded_context: dict[str, dict[str, Any]],
    selected_targets: list[str],
    outcome: dict[str, Any],
) -> dict[str, Any]:
    revised = dict(architecture_decision)
    old_slice = dict(revised.get("first_slice_contract") or {})
    old_targets = [str(item) for item in list(old_slice.get("targets") or [])]
    first_slice = {
        **old_slice,
        "targets": selected_targets,
        "deferred_targets": list(dict.fromkeys(old_targets + list(old_slice.get("deferred_targets") or []))),
        "source": "FirstSliceReselectionRequest + ProjectMapReport expanded evidence",
        "selection_policy": "environment-ready source-backed callable within Architect-expanded candidate window",
        "reselection_iteration": outcome["iteration"],
    }
    source_context = dict(revised.get("source_context") or {})
    source_context.update(expanded_context)
    brief = dict(revised.get("spec_writer_brief") or {})
    brief["first_slice"] = first_slice
    brief["files_or_symbols"] = list(dict.fromkeys(selected_targets + list(brief.get("files_or_symbols") or [])))
    revised.update({
        "first_slice_contract": first_slice,
        "source_context": source_context,
        "spec_writer_brief": brief,
    })
    return _attach_outcome(revised, outcome)


def _attach_outcome(architecture_decision: dict[str, Any], outcome: dict[str, Any]) -> dict[str, Any]:
    revised = dict(architecture_decision)
    history = list(revised.get("first_slice_reselection_history") or [])
    history.append(outcome)
    revised["first_slice_reselection_history"] = history
    return revised
