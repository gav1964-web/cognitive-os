"""Native COS adapters; direct generation receives no COS role artifacts."""
from __future__ import annotations

from evaluation.executors.workspace_agent import run_agent


def execute_route(route, *, root, workspace, prompt, chat, verify):
    if route == 'direct_agent':
        return run_agent(workspace, prompt, chat=chat, verify=verify)
    if route == 'short_chain':
        from .greenfield_role_pipeline import run_greenfield_role_pipeline
        plan = run_greenfield_role_pipeline(root=root, prompt=prompt, write=False,
            use_l45_model=False, require_specific_pattern=False, include_debug_artifacts=True)
        if plan['status'] != 'ok':
            return {'status': 'blocked', 'reason': 'native_short_planning_blocked', 'planning': plan}
        artifacts = plan['_debug_artifacts']
        # Retain actual scope/contracts; do not send the entire diagnostic report
        # (including repeated prompt copies) on every model turn.
        spec = artifacts['product_technical_spec']
        context = {k: spec.get(k) for k in ('artifact_type', 'scope', 'requirements',
                   'primary_contract', 'component_contracts', 'real_world_edge_cases')}
        result = run_agent(workspace, prompt, chat=chat, verify=verify, context=context)
        return {**result, 'planning': plan, 'executor': 'cos_greenfield_plan_plus_workspace_agent.v1'}
    if route != 'full_chain':
        raise ValueError('unknown_route')
    from .role_pipeline import run_role_pipeline
    # This evaluator currently supports a generation task only. Select its actual
    # greenfield contract explicitly; retain default existing-project behavior.
    pipeline = run_role_pipeline(root=root, project_dir=workspace, goal=prompt,
        write=True, run_executor=True, mode='greenfield', delivery_verifier=verify)
    return {'status': pipeline['status'], 'reason': pipeline.get('reason'),
            'executor': pipeline['executor'], 'pipeline': pipeline,
            'verification': pipeline['artifacts'].get('test_result')}
