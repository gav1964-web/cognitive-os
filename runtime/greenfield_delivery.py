"""Explicit native greenfield delivery for configuration-bound sandbox operations."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from .greenfield_delivery_contracts import (
    bind_implementation, file_inventory, review_delivery, validate_output,
)
from .greenfield_role_pipeline import run_greenfield_role_pipeline
from .llm_sandbox_implementation import run_llm_sandbox_implementation


def run_greenfield_delivery(*, root, project_dir, goal, write=False,
                           run_executor=False, verify=None):
    report = {'artifact_type': 'GreenfieldDeliveryReport', 'kind': 'greenfield_delivery',
              'status': 'blocked', 'next_action': 'review_greenfield_handoff',
              'executor': 'native_greenfield_bounded_delivery.v1',
              'goal': goal, 'project': str(project_dir), 'artifacts': {},
              'safety': {'llm_invoked': False, 'registry_changes': False,
                         'implementation_started': False},
              'scope': 'Configuration-bound generator with explicit review; not a general LLM full chain'}
    # Admission occurs before any project writes or expensive inference.
    output = validate_output(root, project_dir)
    planning = run_greenfield_role_pipeline(root=root, prompt=goal, write=False,
        use_l45_model=False, require_specific_pattern=True, include_debug_artifacts=True)
    report['planning'] = planning
    artifacts = report['artifacts']
    artifacts.update(planning['_debug_artifacts'])
    spec = artifacts['product_technical_spec']
    if planning['status'] != 'ok' or spec is None:
        report.update(reason='greenfield_planning_not_ready', next_action=planning['next_action'])
    else:
        preview = run_llm_sandbox_implementation(root=root, prompt=goal, write=False, use_model=False)
        handoff = bind_implementation(spec, preview)
        artifacts['implementation_handoff'] = handoff
        artifacts['test_plan'] = handoff['test_plan']
        if handoff['status'] != 'ready':
            report['reason'] = 'greenfield_implementation_contract_mismatch'
        elif not run_executor:
            report.update(status='planned', next_action='execute_greenfield_handoff')
        elif not write or verify is None:
            report['reason'] = 'explicit_write_and_external_verifier_required'
        else:
            _execute(report, root, output, goal, spec, handoff, verify)
    if write:
        folder = root / 'artifacts/roles/greenfield_delivery'
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.json')
        report['report_path'] = str(target)
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return report


def _execute(report, root, output, goal, spec, handoff, verify):
    # Recheck the new-project boundary immediately before the native writer.
    validate_output(root, output)
    report['safety']['implementation_started'] = True
    execution = run_llm_sandbox_implementation(root=root, prompt=goal, write=True,
                                              output_dir=output, use_model=False)
    report['artifacts']['implementation_result'] = execution
    before = file_inventory(output)
    try:
        verification = verify(output)
    except Exception as exc:
        verification = {'status': 'failed', 'error_type': type(exc).__name__}
    report['artifacts']['test_result'] = verification
    review = review_delivery(spec, handoff, execution, verification, output, before)
    report['artifacts']['review'] = review
    if review['status'] == 'approved':
        report.update(status='completed', next_action='delivery_ready')
    else:
        report.update(reason='greenfield_delivery_review_failed', next_action='rework_greenfield_delivery')
