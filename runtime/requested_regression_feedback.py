"""Bind rejected requested-acceptance observations without restoring delivery authority."""
from pathlib import Path

from .narrow_type_evidence_binding import content_digest
from .repair_trial_binding import validate_repair_trial_source
from .stage_finalization_workspace import inventory, owned_path
from .upstream_llm_candidates import validate_model_candidate
from .upstream_model_delivery import selected_model_candidate
from .upstream_requested_acceptance import requested_test_bindings, test_outcome
from .upstream_task_contract import normalize_task_contract


def requested_regression_inputs(project, run):
    issues = [i for i in run.get('diagnosis', {}).get('issues', [])
              if i.get('failure_specific_reducer_required')]
    if len(issues) != 1:
        raise ValueError('verified_targeted_candidate_with_native_regression_required')
    issue = issues[0]
    request = issue.get('requested_change') or {}
    proof = request.get('acceptance') or {}
    packet = issue.get('failure_evidence_packet') or {}
    comparison = issue.get('causal_comparison') or {}
    if (request.get('reason') != 'requested_behavior_not_verified'
            or request.get('execution_authorized') is not False
            or issue.get('model_delivery') is not None or proof.get('status') != 'failed'
            or proof.get('receipt_digest') != content_digest({k:v for k,v in proof.items() if k!='receipt_digest'})
            or request.get('request_digest') != content_digest({k:v for k,v in request.items() if k!='request_digest'})):
        raise ValueError('verified_targeted_candidate_with_native_regression_required')
    checks = proof.get('checks') or {}
    required = ('interfaces_preserved','sources_unchanged','baseline_expectations_met',
                'baseline_completed','collection_preserved','requested_nodes_executed')
    if not all(checks.get(k) is True for k in required) or checks.get('requested_tests_passed') is not False:
        raise ValueError('requested_regression_preconditions_not_met')
    before = inventory(project)
    contract = normalize_task_contract(request['contract'])
    bindings = requested_test_bindings(contract, before)
    selected = selected_model_candidate(comparison, packet)
    validate_repair_trial_source(project, packet)
    if (proof.get('bindings') != bindings or proof.get('task_contract_digest') != contract['contract_digest']
            or selected['provenance'].get('task_contract_digest') != contract['contract_digest']
            or proof.get('source_inventory_digest') != content_digest(before)
            or proof.get('patched_inventory_digest') != selected['evidence']['patched_inventory_digest']):
        raise ValueError('requested_regression_binding_mismatch')
    patched = Path(selected['patched_project']).resolve(strict=True)
    if patched == project or patched.is_relative_to(project) or project.is_relative_to(patched):
        raise ValueError('external_delivered_candidate_required')
    after = inventory(patched)
    if content_digest(after) != proof['patched_inventory_digest']:
        raise ValueError('requested_regression_candidate_changed')
    target = packet['target']
    path = target.partition(':')[0]
    validate_model_candidate({**selected,'replacement_source':owned_path(patched,path).read_bytes().decode('utf-8')},
                             packet,owned_path(project,path).read_bytes().decode('utf-8'))
    probes = proof.get('probes') or []
    if len(probes) != 2:
        raise ValueError('requested_regression_probes_required')
    nodes = [r['nodeid'] for r in bindings if r['baseline_expectation']=='passes'
             and test_outcome(probes[0],r['nodeid'])=='passes'
             and test_outcome(probes[1],r['nodeid'])=='fails']
    metadata = {'target':target,'task_contract_digest':contract['contract_digest'],
                'delivery_digest':None,'patched_inventory_digest':proof['patched_inventory_digest'],
                'rejection_stage':'requested_acceptance','acceptance_receipt_digest':proof['receipt_digest']}
    return before, selected, metadata, patched, nodes
