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
    analyzer_config: LocalInferenceConfig | None = None,
    spec_writer_advisory_config: LocalInferenceConfig | None = None,
    use_role_llm: bool = False,
    research_requests: list[dict] | None = None,
    mode: str = "existing_project",
    delivery_verifier=None,
    task_contract: dict | None = None,
    product_context: dict | None = None,
) -> dict[str, Any]:
    if (task_contract is not None or product_context is not None) and (mode != 'existing_project' or run_executor or run_transform or force_transform):
        raise ValueError('task_contract_requires_design_validation_before_execution')
    if mode == "greenfield":
        if research_requests or use_role_llm or any((analyzer_config, architect_advisory_config, spec_writer_advisory_config)):
            raise ValueError('upstream_role_llm_requires_existing_project_mode')
        from .greenfield_delivery import run_greenfield_delivery
        if run_transform or force_transform:
            raise ValueError("greenfield_delivery_does_not_promote_or_transform_existing_source")
        return run_greenfield_delivery(root=root, project_dir=project_dir, goal=goal,
            write=write, run_executor=run_executor, verify=delivery_verifier)
    if mode != "existing_project":
        raise ValueError("unknown_role_pipeline_mode")
    load_skill_registry(root)
    from .role_inference import role_model_config, traced_role_config
    events = []
    configs = {'analyzer': analyzer_config, 'architect': architect_advisory_config,
               'spec_writer': spec_writer_advisory_config}
    for role, config in configs.items():
        selected = config or (role_model_config(role) if use_role_llm else None)
        configs[role] = traced_role_config(role, selected, events) if selected else None
    from .role_inference import prepare_role_research
    research = prepare_role_research(research_requests if research_requests is not None else [], configs, root)
    state = {
        "root": root,
        "project_dir": project_dir,
        "goal": goal,
        "write": write,
        "run_transform": run_transform,
        "run_executor": run_executor,
        "force_transform": force_transform,
        "architect_advisory_config": configs['architect'],
        "analyzer_config": configs['analyzer'],
        "spec_writer_advisory_config": configs['spec_writer'],
        "role_research": research,
    }
    if task_contract is not None:
        state['task_contract'] = task_contract
    if product_context is not None:
        state['product_context'] = product_context
    if any(configs.values()):
        state['role_inference'] = {
            'routes': {role: {'model': cfg.model, 'provider_label': cfg.provider_label,
                             'fallback_models': [backup.model for backup in cfg.fallbacks],
                             'fallback_on_codes': list(cfg.fallback_on_codes)}
                       for role, cfg in configs.items() if cfg},
            'events': events,
            'quality_evaluation': 'not_evaluated',
        }
    run_configured_workflow(state=state)
    return dict(state['result'])
