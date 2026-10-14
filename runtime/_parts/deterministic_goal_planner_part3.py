from __future__ import annotations

from dataclasses import asdict
from typing import Any
from runtime.graph_planner import plan_from_spec
from runtime.models import Pipeline
from runtime.pipeline import validate_pipeline
from runtime.registry import CapabilityRegistry

def _target_language_for_goal(goal: str) -> str:
    normalized = goal.lower()
    if "german" in normalized or "deutsch" in normalized or "немец" in normalized:
        return "German"
    return "$input.target_language"

def _pipeline_to_dict(pipeline: Pipeline) -> dict[str, Any]:
    return {
        "id": pipeline.id,
        "version": pipeline.version,
        "nodes": [asdict(node) for node in pipeline.nodes],
        "edges": pipeline.edges,
        "retry_policy": pipeline.retry_policy,
    }
