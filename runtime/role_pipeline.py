"""Orchestrate deterministic role skills into one artifact pipeline."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .local_inference import LocalInferenceConfig
from .role_skill_common import load_skill_registry
from .role_workflow_interpreter import run_configured_workflow


def run_role_pipeline(
    *,
    root: Path,
    project_dir: Path,
    goal: str,
    write: bool = False,
    run_transform: bool = False,
    run_executor: bool = False,
    force_transform: bool = False,
    architect_advisory_config: LocalInferenceConfig | None = None,
    mode: str = "existing_project",
    delivery_verifier=None,
    task_contract: dict | None = None,
    product_context: dict | None = None,
) -> dict[str, Any]:
    if (task_contract is not None or product_context is not None) and (mode != 'existing_project' or run_executor or run_transform or force_transform):
        raise ValueError('task_contract_requires_design_validation_before_execution')
    if mode == "greenfield":
        from .greenfield_delivery import run_greenfield_delivery
        if run_transform or force_transform:
            raise ValueError("greenfield_delivery_does_not_promote_or_transform_existing_source")
        return run_greenfield_delivery(root=root, project_dir=project_dir, goal=goal,
            write=write, run_executor=run_executor, verify=delivery_verifier)
    if mode != "existing_project":
        raise ValueError("unknown_role_pipeline_mode")
    load_skill_registry(root)
    state = {
        "root": root,
        "project_dir": project_dir,
        "goal": goal,
        "write": write,
        "run_transform": run_transform,
        "run_executor": run_executor,
        "force_transform": force_transform,
        "architect_advisory_config": architect_advisory_config,
    }
    if task_contract is not None:
        state['task_contract'] = task_contract
    if product_context is not None:
        state['product_context'] = product_context
    run_configured_workflow(state=state)
    return dict(state["result"])
