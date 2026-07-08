"""Level 3.5 LLM-backed graph planner boundary."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from .graph_planner import plan_from_spec
from .local_inference import LocalInferenceConfig, LocalInferenceError, call_json_chat
from .models import Pipeline
from .pipeline import validate_pipeline
from .registry import CapabilityRegistry


def plan_pipeline_with_llm(
    goal: str,
    registry: CapabilityRegistry,
    *,
    config: LocalInferenceConfig | None = None,
    memory_hint: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Ask a local model for a structured goal spec, then validate Pipeline DSL.

    The model is not allowed to emit executable code or mutate registry state.
    Its output is treated as an untrusted JSON proposal and converted through
    the deterministic graph planner before runtime validation.
    """

    proposal = call_json_chat(_messages(goal, registry, memory_hint=memory_hint), config=config)
    if "steps" not in proposal:
        raise LocalInferenceError("LLM planner response must contain steps")
    planned = plan_from_spec(proposal, registry)
    pipeline = planned["pipeline"]
    validate_pipeline(pipeline, registry)
    return {
        "status": "planned",
        "goal": goal,
        "proposal": proposal,
        "pipeline": _pipeline_to_dict(pipeline),
        "selection": planned["selection"],
    }


def _messages(goal: str, registry: CapabilityRegistry, *, memory_hint: dict[str, Any] | None = None) -> list[dict[str, str]]:
    catalog = [
        {
            "id": capability.id,
            "input_schema": capability.input_schema,
            "output_schema": capability.output_schema,
            "status": capability.lifecycle_status,
            "score": list(registry.score_capability(capability)),
        }
        for capability in sorted(registry.capabilities.values(), key=registry.score_capability, reverse=True)
        if capability.lifecycle_status in {"active", "degraded"}
    ]
    return [
        {
            "role": "system",
            "content": (
                "You are Cognitive OS Level 3.5. Return only JSON. "
                "Do not write code. Do not invent capabilities. "
                "Return an object with keys id, version, steps, retry_policy. "
                "steps must be a list of objects: id, capability, input. "
                "Use only capability ids from the provided catalog. "
                "Use references like $input.name or $nodes.node_id.output.field."
            ),
        },
        {
            "role": "user",
            "content": (
                "Goal:\n"
                f"{goal}\n\n"
                "Capability catalog JSON:\n"
                f"{catalog}\n\n"
                "Memory hint JSON:\n"
                f"{memory_hint or {}}\n\n"
                "Return the smallest valid plan."
            ),
        },
    ]


def _pipeline_to_dict(pipeline: Pipeline) -> dict[str, Any]:
    return {
        "id": pipeline.id,
        "version": pipeline.version,
        "nodes": [asdict(node) for node in pipeline.nodes],
        "edges": pipeline.edges,
        "retry_policy": pipeline.retry_policy,
    }
