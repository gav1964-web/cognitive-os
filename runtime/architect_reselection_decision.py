"""Builders for revised architecture decisions after first-slice reselection."""

from __future__ import annotations

from typing import Any


def revised_architecture_decision(
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
        "steps": reselection_steps(selected_targets[0]),
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
        revised["architecture_synthesis"] = reselection_synthesis(project_report, selected_targets)
    return attach_outcome(revised, outcome)


def reselection_synthesis(project_report: dict[str, Any], selected_targets: list[str]) -> dict[str, Any]:
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


def reselection_steps(target: str) -> list[str]:
    return [
        f"Confirm `{target}` has a stable input/output contract from source evidence.",
        f"Keep writable scope limited to `{target}` until TechnicalSpec acceptance passes.",
        "Map caller and callee context before implementation handoff.",
        "Add contract tests for the selected capability before promotion.",
    ]


def attach_outcome(architecture_decision: dict[str, Any], outcome: dict[str, Any]) -> dict[str, Any]:
    revised = dict(architecture_decision)
    history = list(revised.get("first_slice_reselection_history") or [])
    history.append(outcome)
    revised["first_slice_reselection_history"] = history
    return revised
