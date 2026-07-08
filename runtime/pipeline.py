"""Pipeline DSL loading and input resolution."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .contract_registry import ContractRegistryError, validate_pipeline_contracts
from .models import ExecutionContext, Pipeline, PipelineNode
from .registry import CapabilityRegistry


class PipelineValidationError(ValueError):
    """Raised when Pipeline DSL is invalid for MVP execution."""


def load_pipeline(path: Path) -> Pipeline:
    data = json.loads(path.read_text(encoding="utf-8"))
    return Pipeline(
        id=str(data["id"]),
        version=str(data["version"]),
        nodes=[PipelineNode(id=str(item["id"]), capability=str(item["capability"]), input=dict(item["input"])) for item in data["nodes"]],
        edges=[list(edge) for edge in data.get("edges", [])],
        retry_policy=dict(data.get("retry_policy", {})),
    )


def resolve_node_input(context: ExecutionContext, mapping: dict[str, Any]) -> dict[str, Any]:
    return {key: _resolve_value(context, value) for key, value in mapping.items()}


def validate_pipeline(pipeline: Pipeline, registry: CapabilityRegistry) -> None:
    if not pipeline.nodes:
        raise PipelineValidationError("pipeline must contain at least one node")
    try:
        validate_pipeline_contracts(pipeline, registry)
    except ContractRegistryError as exc:
        raise PipelineValidationError(str(exc)) from exc
    node_ids = [node.id for node in pipeline.nodes]
    if len(set(node_ids)) != len(node_ids):
        raise PipelineValidationError("pipeline node ids must be unique")
    known_ids = set(node_ids)
    for node in pipeline.nodes:
        if node.capability not in registry.capabilities:
            raise PipelineValidationError(f"node {node.id} references missing capability: {node.capability}")
        status = registry.capabilities[node.capability].lifecycle_status
        if status not in {"active", "degraded"}:
            raise PipelineValidationError(f"node {node.id} capability is not active: {node.capability}:{status}")
        _validate_input_refs(node.id, node.input, known_ids)
    edges = _validate_edges(pipeline.edges, known_ids)
    _topological_order(node_ids, edges)
    for node in pipeline.nodes:
        refs = _node_output_refs(node.input)
        dependencies = _transitive_dependencies(node.id, edges)
        for ref in refs:
            if ref == node.id:
                raise PipelineValidationError(f"node {node.id} cannot reference itself")
            if ref not in dependencies:
                raise PipelineValidationError(f"node {node.id} references {ref} without a dependency edge")


def topological_node_batches(pipeline: Pipeline) -> list[list[PipelineNode]]:
    node_by_id = {node.id: node for node in pipeline.nodes}
    edges = [(edge[0], edge[1]) for edge in pipeline.edges]
    batches: list[list[PipelineNode]] = []
    remaining = set(node_by_id)
    completed: set[str] = set()
    while remaining:
        ready = sorted(
            node_id
            for node_id in remaining
            if all(left in completed for left, right in edges if right == node_id)
        )
        if not ready:
            raise PipelineValidationError("pipeline DAG contains a cycle")
        batches.append([node_by_id[node_id] for node_id in ready])
        completed.update(ready)
        remaining.difference_update(ready)
    return batches


def topological_nodes(pipeline: Pipeline) -> list[PipelineNode]:
    return [node for batch in topological_node_batches(pipeline) for node in batch]


def _resolve_value(context: ExecutionContext, value: Any) -> Any:
    if not isinstance(value, str) or not value.startswith("$"):
        return value
    parts = value[1:].split(".")
    if parts[0] == "input":
        current: Any = context.root_input
        for part in parts[1:]:
            current = current[part]
        return current
    if parts[0] == "nodes":
        node_id = parts[1]
        current = context.node_outputs[node_id]
        for part in parts[3:] if len(parts) > 2 and parts[2] == "output" else parts[2:]:
            current = current[part]
        return current
    raise ValueError(f"unsupported reference: {value}")


def _validate_input_refs(node_id: str, mapping: dict[str, Any], known_ids: set[str]) -> None:
    for value in mapping.values():
        if not isinstance(value, str) or not value.startswith("$"):
            continue
        parts = value[1:].split(".")
        if parts[0] == "input":
            if len(parts) < 2:
                raise PipelineValidationError(f"node {node_id} has empty input reference")
            continue
        if parts[0] == "nodes":
            if len(parts) < 3 or parts[2] != "output":
                raise PipelineValidationError(f"node {node_id} has invalid node output reference: {value}")
            if parts[1] not in known_ids:
                raise PipelineValidationError(f"node {node_id} references unknown node: {parts[1]}")
            continue
        raise PipelineValidationError(f"node {node_id} has unsupported reference: {value}")


def _validate_edges(edges: list[list[str]], known_ids: set[str]) -> list[tuple[str, str]]:
    normalized: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for edge in edges:
        if len(edge) != 2:
            raise PipelineValidationError("pipeline edges must contain exactly two node ids")
        left, right = str(edge[0]), str(edge[1])
        if left not in known_ids or right not in known_ids:
            raise PipelineValidationError(f"pipeline edge references unknown node: {left}->{right}")
        if left == right:
            raise PipelineValidationError(f"pipeline edge cannot be self-referential: {left}")
        pair = (left, right)
        if pair in seen:
            raise PipelineValidationError(f"pipeline edge is duplicated: {left}->{right}")
        seen.add(pair)
        normalized.append(pair)
    return normalized


def _topological_order(node_ids: list[str], edges: list[tuple[str, str]]) -> list[str]:
    remaining = set(node_ids)
    completed: list[str] = []
    completed_set: set[str] = set()
    while remaining:
        ready = sorted(
            node_id
            for node_id in remaining
            if all(left in completed_set for left, right in edges if right == node_id)
        )
        if not ready:
            raise PipelineValidationError("pipeline DAG contains a cycle")
        completed.extend(ready)
        completed_set.update(ready)
        remaining.difference_update(ready)
    return completed


def _node_output_refs(mapping: dict[str, Any]) -> set[str]:
    refs: set[str] = set()
    for value in mapping.values():
        if not isinstance(value, str) or not value.startswith("$nodes."):
            continue
        parts = value[1:].split(".")
        refs.add(parts[1])
    return refs


def _transitive_dependencies(node_id: str, edges: list[tuple[str, str]]) -> set[str]:
    direct = {left for left, right in edges if right == node_id}
    dependencies = set(direct)
    frontier = list(direct)
    while frontier:
        current = frontier.pop()
        for parent, child in edges:
            if child == current and parent not in dependencies:
                dependencies.add(parent)
                frontier.append(parent)
    return dependencies
