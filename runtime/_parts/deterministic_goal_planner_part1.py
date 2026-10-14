from __future__ import annotations

from dataclasses import asdict
from typing import Any
from runtime.graph_planner import plan_from_spec
from runtime.models import Pipeline
from runtime.pipeline import validate_pipeline
from runtime.registry import CapabilityRegistry

def plan_from_required_capabilities(
    goal: str,
    required_capabilities: list[str],
    registry: CapabilityRegistry,
) -> dict[str, Any] | None:
    proposal = _proposal_for(goal, required_capabilities)
    if proposal is None:
        return None
    planned = plan_from_spec(proposal, registry)
    pipeline = planned["pipeline"]
    validate_pipeline(pipeline, registry)
    return {
        "status": "planned",
        "goal": goal,
        "proposal": proposal,
        "pipeline": _pipeline_to_dict(pipeline),
        "selection": planned["selection"],
        "planner": "deterministic_required_capabilities",
    }
