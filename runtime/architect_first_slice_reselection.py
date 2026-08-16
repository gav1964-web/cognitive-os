"""Architect-owned expansion of a rejected first-slice candidate window."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .project_probe_env import declared_project_packages
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
    declared = declared_project_packages(Path(project_root)) if project_root else set()
    eligible = [
        source
        for source in sources
        if _environment_ready_callable(expanded_context.get(source))
        or _declared_dependency_callable(expanded_context.get(source), declared, policy)
    ]
    selected = eligible[: max(1, int(policy.get("selected_target_limit") or 8))]
    _mark_manifest_declared_context(selected, expanded_context, declared, policy)
    evidence = {
        "artifact_type": "FirstSliceReselectionOutcome",
        "iteration": iteration,
        "status": "selected" if selected else "exhausted",
        "trigger": request.get("trigger"),
        "expanded_candidate_count": len(sources),
        "environment_ready_candidate_count": len(ready),
        "declared_dependency_candidate_count": len(set(eligible) - set(ready)),
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
        project_report=project_report,
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


def _declared_dependency_callable(
    context: dict[str, Any] | None,
    declared_packages: set[str],
    policy: dict[str, Any],
) -> bool:
    if not policy.get("allow_declared_dependency_candidates", False):
        return False
    row = dict(context or {})
    snippet = dict(row.get("snippet") or {})
    readiness = dict(row.get("dependency_readiness") or {})
    missing = {_normalize_distribution(item) for item in readiness.get("missing_external_modules") or []}
    eligibility = standalone_target_eligibility({"target_binding": snippet.get("target_binding")})
    return bool(
        missing
        and missing <= declared_packages
        and row.get("node_kind") == "function"
        and snippet.get("text")
        and eligibility.get("eligible")
    )


def _normalize_distribution(value: Any) -> str:
    return str(value).replace("_", "-").lower()


def _mark_manifest_declared_context(
    selected: list[str],
    expanded_context: dict[str, dict[str, Any]],
    declared_packages: set[str],
    policy: dict[str, Any],
) -> None:
    for source in selected:
        row = dict(expanded_context.get(source) or {})
        if not _declared_dependency_callable(row, declared_packages, policy):
            continue
        readiness = dict(row.get("dependency_readiness") or {})
        readiness.update({
            "status": "manifest_declared",
            "declaration_source": "project dependency manifests",
            "executable_probe_required": True,
        })
        row["dependency_readiness"] = readiness
        expanded_context[source] = row


def _revised_architecture_decision(
    architecture_decision: dict[str, Any],
    *,
    project_report: dict[str, Any],
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
        "steps": _reselection_steps(selected_targets[0]),
        "source": "FirstSliceReselectionRequest + ProjectMapReport expanded evidence",
        "selection_policy": "environment-ready or manifest-backed callable within Architect-expanded candidate window",
        "reselection_iteration": outcome["iteration"],
    }
    source_context = dict(revised.get("source_context") or {})
    source_context.update(expanded_context)
    brief = dict(revised.get("spec_writer_brief") or {})
    brief["first_slice"] = first_slice
    brief["acceptance_targets"] = [
        f"Reselected first slice verifies step {index}: {step}"
        for index, step in enumerate(first_slice["steps"], start=1)
    ]
    brief["files_or_symbols"] = list(dict.fromkeys(selected_targets + list(brief.get("files_or_symbols") or [])))
    revised.update({
        "first_slice_contract": first_slice,
        "source_context": source_context,
        "spec_writer_brief": brief,
    })
    if not dict(revised.get("architecture_synthesis") or {}):
        revised["architecture_synthesis"] = _reselection_synthesis(project_report, selected_targets)
    return _attach_outcome(revised, outcome)


def _reselection_synthesis(
    project_report: dict[str, Any], selected_targets: list[str]
) -> dict[str, Any]:
    summary = dict(project_report.get("summary") or {})
    scope = dict(dict(project_report.get("answers") or {}).get("1_scope") or {})
    domain = dict(scope.get("domain_profile") or {})
    archetype = str(domain.get("kind") or summary.get("project_shape") or "python_project")
    return {
        "artifact_type": "ProjectArchitectureSynthesis",
        "source": "Architect.first_slice_reselection",
        "synthesis_id": "reselection_source_backed_synthesis",
        "confidence": 0.82,
        "project_profile": {
            "archetype": archetype,
            "entrypoints": list(summary.get("entrypoints") or [])[:6],
            "languages": list(summary.get("languages") or [])[:6],
            "evidence": selected_targets[:8],
            "domain_profile": domain,
        },
        "project_diagnosis": "Initial slice had no safe callable; Architect selected a source-backed expanded candidate window.",
        "target_architecture_shape": [
            "Keep the reselected callable boundary explicit.",
            "Isolate declared external dependencies behind validation gates.",
            "Preserve deferred targets outside the first writable scope.",
        ],
    }


def _reselection_steps(target: str) -> list[str]:
    return [
        f"Confirm `{target}` has a stable input/output contract from source evidence.",
        f"Keep writable scope limited to `{target}` until TechnicalSpec acceptance passes.",
        "Map caller and callee context before implementation handoff.",
        "Add contract tests for the selected capability before promotion.",
    ]


def _attach_outcome(architecture_decision: dict[str, Any], outcome: dict[str, Any]) -> dict[str, Any]:
    revised = dict(architecture_decision)
    history = list(revised.get("first_slice_reselection_history") or [])
    history.append(outcome)
    revised["first_slice_reselection_history"] = history
    return revised
