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
) -> dict[str, Any]:
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
    run_configured_workflow(state=state)
    return dict(state["result"])
