"""Bounded source-bound feedback requests; contradictory evidence reopens analysis."""
from copy import deepcopy

from .narrow_type_evidence_binding import content_digest


def build_upstream_feedback(*, analysis: dict, architecture: dict, specification: dict,
                            observations: list[dict] | None = None, previous: dict | None = None) -> dict:
    contract = analysis.get('task_contract') or {}
    bindings = {r['target']: r['file_sha256'] for r in analysis.get('task_analysis', {}).get('source_facts', [])}
    iteration = (previous or {}).get('iteration', 0)
    if type(iteration) is not int or not 0 <= iteration <= 2:
        raise ValueError('invalid_feedback_iteration')
    if previous and previous.get('contract_digest') != contract.get('contract_digest'):
        raise ValueError('feedback_contract_changed')
    rows = observations or []
    if len(rows) > 16:
        raise ValueError('feedback_observation_limit')
    accepted, rejected = [], []
    for row in rows:
        valid = (isinstance(row, dict) and row.get('target') in bindings
                 and row.get('file_sha256') == bindings.get(row.get('target'))
                 and row.get('outcome') in {'supports', 'contradicts', 'inconclusive'}
                 and isinstance(row.get('receipt_digest'), str) and row['receipt_digest'].startswith('sha256:'))
        (accepted if valid else rejected).append(deepcopy(row))
    requests = []
    task = analysis.get('task_analysis', {})
    if task.get('status') != 'source_bound' or any(r['outcome'] == 'contradicts' for r in accepted):
        requests.append({'role': 'analyzer', 'action': 'Recheck conflicting requirements, source scope or contradicted hypothesis.',
                         'reason': 'observation_or_input_requires_revision'})
    if specification.get('task_handoff', {}).get('gaps'):
        requests.append({'role': 'architect', 'action': 'Specify implementation mechanism, affected callers and preserved effects.',
                         'reason': 'design_not_validated'})
    for gap in specification.get('task_handoff', {}).get('gaps', []):
        if gap.get('requirement_id'):
            requests.append({'role': 'spec_writer', 'action': 'Specify an observable acceptance condition.', **gap})
    result = {'schema_version': 'upstream_role_feedback.v1', 'iteration': iteration + 1,
        'status': 'retry_budget_exhausted' if iteration >= 2 else 'review_requested',
        'contract_digest': contract.get('contract_digest'), 'source_bindings': bindings,
        'accepted_observations': accepted, 'rejected_observations': rejected, 'requests': requests,
        'observation_authority': 'caller_supplied_reference; receipt contents not independently verified here',
        'automatic_retry': False, 'execution_authorized': False}
    result['feedback_digest'] = content_digest(result)
    return result
