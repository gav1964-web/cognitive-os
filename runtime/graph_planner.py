"""Rule-based graph planner over Capability Registry schemas."""

from __future__ import annotations

from typing import Any

from .models import Capability, Pipeline, PipelineNode
from .registry import CapabilityRegistry


class GraphPlanningError(RuntimeError):
    """Raised when no deterministic graph rule can satisfy a goal."""


def plan_pipeline(goal: str, registry: CapabilityRegistry) -> Pipeline:
    active = {key for key, value in registry.capabilities.items() if value.lifecycle_status == "active"}
    if goal == "normalize_then_hash":
        _require(active, "normalize_text")
        _require(active, "hash_payload")
        return Pipeline(
            id="normalize_then_hash",
            version="0.1.0",
            nodes=[
                PipelineNode(id="normalize", capability="normalize_text", input={"text": "$input.text"}),
                PipelineNode(id="hash", capability="hash_payload", input={"value": "$nodes.normalize.output.text"}),
            ],
            edges=[["normalize", "hash"]],
            retry_policy={"max_attempts": 1, "retry_on": ["transient"]},
        )
    if goal == "select_then_hash":
        _require(active, "json_select")
        _require(active, "hash_payload")
        return Pipeline(
            id="select_then_hash",
            version="0.1.0",
            nodes=[
                PipelineNode(id="select", capability="json_select", input={"data": "$input.data", "path": "$input.path"}),
                PipelineNode(id="hash", capability="hash_payload", input={"value": "$nodes.select.output.value"}),
            ],
            edges=[["select", "hash"]],
            retry_policy={"max_attempts": 1, "retry_on": ["transient"]},
        )
    if goal == "markdown_file_to_text_file":
        for capability_id in ("read_text_file", "markdown_to_text", "write_text_file"):
            _require(active, capability_id)
        return Pipeline(
            id="markdown_file_to_text_file",
            version="0.1.0",
            nodes=[
                PipelineNode(id="read", capability="read_text_file", input={"path": "$input.input_path"}),
                PipelineNode(id="convert", capability="markdown_to_text", input={"markdown": "$nodes.read.output.text"}),
                PipelineNode(
                    id="write",
                    capability="write_text_file",
                    input={"path": "$input.output_path", "text": "$nodes.convert.output.text"},
                ),
            ],
            edges=[["read", "convert"], ["convert", "write"]],
            retry_policy={"max_attempts": 1, "retry_on": ["transient"]},
        )
    if goal == "markdown_file_to_rtf_file":
        for capability_id in ("read_text_file", "markdown_to_rtf", "write_text_file"):
            _require(active, capability_id)
        return Pipeline(
            id="markdown_file_to_rtf_file",
            version="0.1.0",
            nodes=[
                PipelineNode(id="read", capability="read_text_file", input={"path": "$input.input_path"}),
                PipelineNode(id="convert", capability="markdown_to_rtf", input={"markdown": "$nodes.read.output.text"}),
                PipelineNode(
                    id="write",
                    capability="write_text_file",
                    input={"path": "$input.output_path", "text": "$nodes.convert.output.rtf"},
                ),
            ],
            edges=[["read", "convert"], ["convert", "write"]],
            retry_policy={"max_attempts": 1, "retry_on": ["transient"]},
        )
    if goal == "fetch_links":
        _require(active, "fetch_html")
        _require(active, "extract_links")
        return Pipeline(
            id="fetch_links",
            version="0.1.0",
            nodes=[
                PipelineNode(id="fetch", capability="fetch_html", input={"url": "$input.url"}),
                PipelineNode(id="links", capability="extract_links", input={"html": "$nodes.fetch.output.html"}),
            ],
            edges=[["fetch", "links"]],
            retry_policy={"max_attempts": 1, "retry_on": ["transient"]},
        )
    if goal == "spreadsheet_to_csv":
        _require(active, "spreadsheet_to_csv")
        return Pipeline(
            id="spreadsheet_to_csv",
            version="0.1.0",
            nodes=[
                PipelineNode(
                    id="spreadsheet_to_csv",
                    capability="spreadsheet_to_csv",
                    input={"input_path": "$input.input_path", "output_path": "$input.output_path"},
                )
            ],
            edges=[],
            retry_policy={"max_attempts": 1, "retry_on": ["transient"]},
        )
    if goal == "csv_to_spreadsheet":
        _require(active, "csv_to_spreadsheet")
        return Pipeline(
            id="csv_to_spreadsheet",
            version="0.1.0",
            nodes=[
                PipelineNode(
                    id="csv_to_spreadsheet",
                    capability="csv_to_spreadsheet",
                    input={"input_path": "$input.input_path", "output_path": "$input.output_path"},
                )
            ],
            edges=[],
            retry_policy={"max_attempts": 1, "retry_on": ["transient"]},
        )
    raise GraphPlanningError(f"no graph rule for goal: {goal}")


def plan_from_spec(goal_spec: dict[str, Any], registry: CapabilityRegistry) -> dict[str, Any]:
    """Build a small Pipeline DSL from a structured goal spec.

    Supported MVP shape:
    {"id": "...", "steps": [{"capability": "...", "input": {...}}, ...]}
    Omitted node ids are derived from capability ids. Edges are linear and the
    resulting pipeline is still validated by the runtime before execution.
    """

    goal_id = str(goal_spec.get("id", "planned_pipeline"))
    steps = list(goal_spec.get("steps", []))
    if not steps:
        raise GraphPlanningError("goal spec must contain steps")
    nodes: list[PipelineNode] = []
    explanations: list[dict[str, Any]] = []
    for index, step in enumerate(steps):
        capability_id = str(step["capability"])
        capability = registry.get(capability_id)
        node_id = str(step.get("id") or f"{capability_id}_{index + 1}")
        nodes.append(PipelineNode(id=node_id, capability=capability_id, input=dict(step.get("input", {}))))
        explanations.append(_selection_explanation(registry, capability))
    pipeline = Pipeline(
        id=goal_id,
        version=str(goal_spec.get("version", "0.1.0")),
        nodes=nodes,
        edges=[[left.id, right.id] for left, right in zip(nodes, nodes[1:])],
        retry_policy=dict(goal_spec.get("retry_policy", {"max_attempts": 1, "retry_on": ["transient"]})),
    )
    return {"pipeline": pipeline, "selection": explanations}


def explain_selection(registry: CapabilityRegistry) -> list[dict[str, Any]]:
    return [_selection_explanation(registry, item) for item in sorted(registry.capabilities.values(), key=registry.score_capability, reverse=True)]


def _require(active: set[str], capability_id: str) -> None:
    if capability_id not in active:
        raise GraphPlanningError(f"required capability is not active: {capability_id}")


def _selection_explanation(registry: CapabilityRegistry, capability: Capability) -> dict[str, Any]:
    return {
        "capability_id": capability.id,
        "score": list(registry.score_capability(capability)),
        "status": capability.lifecycle_status,
        "determinism_grade": capability.determinism_grade,
        "side_effects": capability.side_effects,
    }
