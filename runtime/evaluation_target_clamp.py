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
    original_slice = dict(result.get("first_slice_contract") or {})
    original_targets = [
        str(source) for source in original_slice.get("targets") or []
        if str(source) in context and str(source) != target and ":" in str(source)
    ]
    context_candidates = [
        str(source) for source in context
        if str(source) != target and ":" in str(source)
    ]
    candidates = list(dict.fromkeys([*original_targets, *context_candidates]))
    candidate_pool = sorted(
        candidates, key=lambda source: _candidate_pool_rank(source, context)
    )[:8]
    first_slice = _clamped_slice(original_slice, target)
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
            "candidate_pool": candidate_pool,
        },
    })
    return result


def _clamped_slice(value: dict[str, Any], target: str) -> dict[str, Any]:
    return {
        **value,
        "name": value.get("name") or "same_source_evaluation",
        "goal": f"Evaluate the source-backed contract at {target}.",
        "targets": [target],
        "steps": [f"Specify and verify `{target}` without changing project source."],
        "source": "CognitiveSelfImprovement.same_source_evaluation",
    }


def _candidate_pool_rank(
    source: str, context: dict[str, Any]
) -> tuple[int, int, int, int, int, str]:
    evidence = dict(context.get(source) or {})
    snippet = dict(evidence.get("snippet") or {})
    structural = dict(snippet.get("structural_contract") or {})
    effects = list(snippet.get("side_effects") or structural.get("observed_side_effects") or [])
    instance_bound = bool(
        snippet.get("owner_class") or structural.get("owner_class")
        or snippet.get("target_binding") == "method_symbol"
    )
    output_basis = str(structural.get("output_inference_basis") or "")
    return_paths = int(structural.get("return_paths") or 0)
    return (
        int(bool(effects)), int(instance_bound),
        int(output_basis in {"", "insufficient_structural_evidence", "no_value_return"}),
        -return_paths, -int(evidence.get("candidate_score") or 0), source,
    )
