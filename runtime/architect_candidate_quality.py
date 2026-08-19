"""Structural contract quality used by Architect first-slice reselection."""

from __future__ import annotations

from typing import Any

from .source_contract_types import concrete_type
from .target_quality import semantic_target_quality_report


def contract_quality(
    source: str,
    source_context: dict[str, Any] | None,
    candidate_sources: list[str],
) -> dict[str, Any]:
    context = dict(source_context or {})
    snippet = dict(context.get("snippet") or {})
    structural = dict(snippet.get("structural_contract") or context.get("structural_contract") or {})
    signature = dict(snippet.get("signature") or context.get("signature") or {})
    inputs = _input_contract(signature, structural)
    output_type = str(structural.get("inferred_output_type") or "InferredOutput")
    effects = list(context.get("contract_side_effects") or context.get("side_effects") or [])
    quality = semantic_target_quality_report(
        source,
        ranked_candidates=[source, *[item for item in candidate_sources if item != source]],
        source_evidence=candidate_sources,
        selection_reason=str(context.get("kind") or "").replace("_", " "),
        structural_evidence=structural,
        input_contract=inputs,
        output_contract={"result": output_type},
        side_effect_contract={
            "declared": effects,
            "requires_process_boundary": bool(effects),
            "retry_policy": "isolate before retry" if effects else "pure or read-only retry",
        },
    )
    shapes = [*inputs.values(), output_type]
    return {
        "semantic_score": int(quality.get("score") or 0),
        "semantic_status": str(quality.get("status") or ""),
        "contract_shape_score": round(100 * sum(concrete_type(value) for value in shapes) / len(shapes)),
    }


def _input_contract(signature: dict[str, Any], structural: dict[str, Any]) -> dict[str, str]:
    usage = dict(structural.get("argument_usage_types") or {})
    constraints = dict(structural.get("argument_constraint_types") or {})
    documented = dict(structural.get("docstring_argument_types") or {})
    inputs = {}
    for argument in [*list(signature.get("args") or []), *list(signature.get("kwonlyargs") or [])]:
        if not isinstance(argument, dict):
            continue
        name = str(argument.get("name") or "")
        if not name or name in {"self", "cls"}:
            continue
        inputs[name] = (
            str(argument.get("annotation") or "").strip()
            or str(documented.get(name) or "")
            or str(usage.get(name) or "")
            or str(constraints.get(name) or "")
            or "InferredInput"
        )
    return inputs or ({"call_context": "NoArguments"} if "args" in signature else {"call_context": "InferredInput"})
