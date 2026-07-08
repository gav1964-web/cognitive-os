"""Deterministic instantiation of memory-derived plan templates."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from .graph_planner import plan_from_spec
from .models import Pipeline
from .pipeline import validate_pipeline
from .registry import CapabilityRegistry


class TemplateInstantiationError(RuntimeError):
    """Raised when a memory template cannot produce a valid Pipeline DSL."""


def plan_from_memory_template(
    goal: str,
    memory_preflight: dict[str, Any],
    registry: CapabilityRegistry,
    *,
    required_capabilities: list[str] | None = None,
    min_score: float = 0.5,
    min_support: int = 2,
) -> dict[str, Any] | None:
    recommendation = memory_preflight.get("template_recommendation")
    if not isinstance(recommendation, dict):
        return None
    if float(recommendation.get("score", 0.0)) < min_score:
        return None
    if int(recommendation.get("support_count", 0)) < min_support:
        return None
    template = _find_template(memory_preflight, str(recommendation.get("template_id", "")))
    if template is None:
        raise TemplateInstantiationError("recommended template is missing from memory preflight")
    if template.get("safety_status") != "mature":
        raise TemplateInstantiationError(f"template is not mature: {template.get('safety_status')}")
    _validate_required_capabilities(template, required_capabilities or [])
    _validate_template_capabilities(template, registry)
    _reject_stale_project_analysis_template(template)
    proposal = _proposal_from_template(template)
    planned = plan_from_spec(proposal, registry)
    pipeline = planned["pipeline"]
    validate_pipeline(pipeline, registry)
    return {
        "status": "planned",
        "goal": goal,
        "proposal": proposal,
        "pipeline": _pipeline_to_dict(pipeline),
        "selection": planned["selection"],
        "planner": "memory_template",
        "template_id": template.get("template_id"),
        "template_support_count": template.get("support_count"),
    }


def _find_template(memory_preflight: dict[str, Any], template_id: str) -> dict[str, Any] | None:
    for template in memory_preflight.get("template_matches", []):
        if isinstance(template, dict) and template.get("template_id") == template_id:
            return template
    return None


def _proposal_from_template(template: dict[str, Any]) -> dict[str, Any]:
    pipeline_template = dict(template.get("pipeline_template", {}))
    nodes = list(pipeline_template.get("nodes", []))
    if not nodes:
        raise TemplateInstantiationError("template has no nodes")
    return {
        "id": f"template_{template.get('template_id', 'memory')}",
        "version": "0.1.0",
        "steps": [
            {
                "id": str(node["id"]),
                "capability": str(node["capability"]),
                "input": dict(node.get("input", {})),
            }
            for node in nodes
        ],
        "retry_policy": dict(pipeline_template.get("retry_policy", {"max_attempts": 1, "retry_on": ["transient"]})),
    }


def _validate_template_capabilities(template: dict[str, Any], registry: CapabilityRegistry) -> None:
    for capability_id in template.get("capabilities", []):
        capability = registry.capabilities.get(str(capability_id))
        if capability is None:
            raise TemplateInstantiationError(f"template capability is missing: {capability_id}")
        if capability.lifecycle_status != "active":
            raise TemplateInstantiationError(
                f"template capability is not active: {capability_id}:{capability.lifecycle_status}"
            )


def _validate_required_capabilities(template: dict[str, Any], required_capabilities: list[str]) -> None:
    if not required_capabilities:
        return
    template_capabilities = [str(item) for item in template.get("capabilities", [])]
    if template_capabilities != [str(item) for item in required_capabilities]:
        raise TemplateInstantiationError(
            "template capabilities do not match Level 4 required capabilities: "
            f"{template_capabilities} != {required_capabilities}"
        )


def _reject_stale_project_analysis_template(template: dict[str, Any]) -> None:
    capabilities = {str(item) for item in template.get("capabilities", [])}
    if "project_map_report" not in capabilities or "read_many_files" not in capabilities:
        return
    pipeline_template = dict(template.get("pipeline_template", {}))
    for node in pipeline_template.get("nodes", []):
        if str(node.get("capability")) != "read_many_files":
            continue
        node_input = dict(node.get("input", {}))
        if node_input.get("auto_discover") is not True:
            raise TemplateInstantiationError("stale project-analysis template: read_many_files must use auto_discover")


def _pipeline_to_dict(pipeline: Pipeline) -> dict[str, Any]:
    return {
        "id": pipeline.id,
        "version": pipeline.version,
        "nodes": [asdict(node) for node in pipeline.nodes],
        "edges": pipeline.edges,
        "retry_policy": pipeline.retry_policy,
    }
