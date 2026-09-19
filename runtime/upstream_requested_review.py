"""Review native requirement evidence without promoting free-form task claims."""
from .narrow_type_evidence_binding import content_digest
from .review_findings_common import check_row
from .upstream_task_contract import normalize_task_contract
from .upstream_requested_acceptance import test_outcome


def requested_change_checks(spec: dict, acceptance: dict) -> list[dict]:
    valid = False
    try:
        contract = normalize_task_contract(spec['task_contract'])
        request = spec.get('requested_change') or {}
        proof = request.get('acceptance') or {}
        intent = spec.get('implementation_delta', {}).get('intent', {})
        packet = intent.get('failure_evidence_packet') or {}
        requirements = {r['id']: r for r in spec.get('requirements', [])}
        expected = [(r['id'], e['nodeid']) for r in contract['requirements'] for e in r['acceptance_examples']
                    if e['kind'] == 'native_test' and e['expectation'] == 'passes']
        bindings = proof.get('bindings', [])
        nodes = {n for _, n in expected}
        checks = proof.get('checks', {})
        probes = proof.get('probes', [])
        criteria = spec.get('requested_acceptance_criteria', [])
        actual = {c['id']: c for c in spec.get('acceptance_criteria', [])}
        trace = spec.get('requirement_traceability', [])
        authority = intent.get('authority') == 'explicit_training_replay'
        if intent.get('authority') == 'explicit_model_candidate_replay':
            from .upstream_model_requirements import model_request_authority
            authority = model_request_authority(intent, contract, request, proof)
        valid = bool(
            expected and len(expected) == sum(len(r['acceptance_examples']) for r in contract['requirements'])
            and spec.get('contract_mode') == 'failure_repair'
            and authority
            and intent.get('causal_comparison', {}).get('status') == 'selected_for_regression'
            and request.get('status') == 'verified_for_regression'
            and request.get('contract') == contract
            and request.get('request_digest') == content_digest({k: v for k, v in request.items() if k != 'request_digest'})
            and proof.get('status') == 'passed'
            and proof.get('receipt_digest') == content_digest({k: v for k, v in proof.items() if k != 'receipt_digest'})
            and proof.get('task_contract_digest') == contract['contract_digest']
            and proof.get('source_inventory_digest') == packet.get('project_inventory_digest')
            and proof.get('impact_digest') == request['impact']['impact_digest']
            and [(r['requirement_id'], r['nodeid']) for r in bindings] == expected
            and [(c['requirement_id'], c['example']['nodeid']) for c in criteria] == expected
            and all(actual.get(c['id']) == c for c in criteria)
            and trace == [{'requirement_id': r['id'], 'targets': r.get('targets', []),
                'acceptance_ids': [c['id'] for c in criteria if c['requirement_id'] == r['id']]}
                for r in contract['requirements']]
            and all(checks.get(k) is True for k in ('interfaces_preserved', 'sources_unchanged',
                'baseline_completed', 'baseline_expectations_met', 'collection_preserved', 'requested_nodes_executed', 'requested_tests_passed'))
            and len(probes) == 2 and set(probes[1]['selected_nodeids']) == nodes
            and all(test_outcome(probes[0], e['nodeid']) == e['baseline_expectation']
                    and test_outcome(probes[1], e['nodeid']) == 'passes'
                    for r in contract['requirements'] for e in r['acceptance_examples'])
            and probes[1]['returncode'] == 0 and probes[1]['passing'] == len(nodes) and probes[1]['skipped'] == 0
            and all(requirements.get(r['id'], {}).get('priority') == 'MUST'
                    and all(requirements[r['id']].get(k) == r.get(k) for k in ('statement', 'targets', 'acceptance_examples'))
                    for r in contract['requirements'])
            and (not acceptance or acceptance.get('patched_inventory_digest') == proof.get('patched_inventory_digest')))
    except (KeyError, ValueError, TypeError, AttributeError):
        valid = False
    return [check_row('requested_change_design_verified', valid,
        'Every explicit requirement must retain its native test evidence and match the executed intervention; semantic test adequacy remains caller supplied.')]
