"""Evaluation-only clamp for same-source role experiments."""

from __future__ import annotations

from typing import Any, Callable


def evaluation_target_transform(
    target: str, source_evidence: dict[str, Any] | None = None
) -> Callable[[dict[str, Any]], dict[str, Any]]:
    def transform(artifact: dict[str, Any]) -> dict[str, Any]:
        if artifact.get("artifact_type") != "ArchitectureDecisionRecord":
            return artifact
        return clamp_architecture_target(artifact, target, source_evidence=source_evidence)

    return transform


def clamp_architecture_target(
    artifact: dict[str, Any], target: str, *, source_evidence: dict[str, Any] | None = None
) -> dict[str, Any]:
    context = dict(artifact.get("source_context") or {})
    if target not in context and not source_evidence:
        return artifact
    if source_evidence:
        context[target] = dict(source_evidence)
    result = dict(artifact)
    first_slice = _clamped_slice(dict(result.get("first_slice_contract") or {}), target)
    brief = dict(result.get("spec_writer_brief") or {})
    brief_slice = _clamped_slice(dict(brief.get("first_slice") or first_slice), target)
    brief.update({
        "first_slice": brief_slice,
        "files_or_symbols": [target],
        "contract_targets": [target],
        "acceptance_targets": [target],
    })
    synthesis = dict(result.get("architecture_synthesis") or {})
    if synthesis:
        synthesis["recommended_first_slice"] = _clamped_slice(
            dict(synthesis.get("recommended_first_slice") or first_slice), target
        )
    result.update({
        "first_slice_contract": first_slice,
        "source_context": context,
        "spec_writer_brief": brief,
        "architecture_synthesis": synthesis,
        "evaluation_target_clamp": {
            "mode": "evaluation_only",
            "target": target,
            "source_context_verified": True,
        },
    })
    return result


def _clamped_slice(value: dict[str, Any], target: str) -> dict[str, Any]:
    steps = list(value.get("steps") or [])
    return {
        **value,
        "name": value.get("name") or "same_source_evaluation",
        "goal": f"Evaluate the source-backed contract at {target}.",
        "targets": [target],
        "steps": steps or [f"Specify and verify `{target}` without changing project source."],
        "source": "CognitiveSelfImprovement.same_source_evaluation",
    }
