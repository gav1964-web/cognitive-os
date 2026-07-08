"""Typed runtime models for the Cognitive OS MVP."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Capability:
    id: str
    version: str
    entrypoint: str
    input_schema_ref: str
    output_schema_ref: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    determinism_grade: str
    side_effects: dict[str, Any]
    lifecycle_status: str
    version_hash: str
    fallback_for: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class PipelineNode:
    id: str
    capability: str
    input: dict[str, Any]


@dataclass(frozen=True)
class Pipeline:
    id: str
    version: str
    nodes: list[PipelineNode]
    edges: list[list[str]]
    retry_policy: dict[str, Any]


@dataclass
class ExecutionContext:
    pipeline: Pipeline
    root_input: dict[str, Any]
    state: str = "READY"
    current_node: str | None = None
    completed_nodes: list[str] = field(default_factory=list)
    node_outputs: dict[str, dict[str, Any]] = field(default_factory=dict)
    retry_counts: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class RuntimeFailure:
    error_class: str
    exception_type: str
    message: str
    traceback_hash: str


@dataclass(frozen=True)
class PolicyDecision:
    action: str
    replacement_capability: str | None = None
    reason_code: str = ""

