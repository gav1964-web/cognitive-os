"""Controller-side reconciliation of a pinned role ledger, including hard exits.

The controller reserves the whole remaining allowance before spawning. A lost
controller never frees that hold while an orphan worker could still be active.
Ledger evidence is from trusted worker code, not provider billing attestation.
"""
from pathlib import Path

from .remote_support_protocol import digest, load


def validate_accounting(policy):
    if policy.get('accounting') not in (None, 'role_ledger.v1'):
        raise ValueError('support_accounting_contract')
    if policy.get('accounting'):
        binding = policy['checkpoint']
        if (set(binding) != {'job_file', 'job_sha256'}
                or not Path(binding['job_file']).is_absolute()):
            raise ValueError('support_accounting_binding')


def ledger_snapshot(policy):
    from .remote_role_job import continuation_ledger
    binding = policy['checkpoint']
    job = load(binding['job_file'])
    if (digest(job) != binding['job_sha256'] or job.get('schema') != 'remote_role_job.v1'
            or job['goal'] != policy['task']
            or digest(Path(job['initial_ledger']).read_bytes()) != job['initial_ledger_sha256']):
        raise ValueError('support_accounting_job_changed')
    path = continuation_ledger(job)
    data = load(path)
    if data.get('schema_version') != 'claim_suite_budget.v1' or not isinstance(data.get('jobs'), dict):
        raise ValueError('support_accounting_ledger_invalid')
    for row in data['jobs'].values():
        if (not isinstance(row, dict) or set(row) != {'state', 'reported_tokens', 'reserved_tokens'}
                or row['state'] not in ('ready', 'started', 'unknown', 'done')
                or type(row['reserved_tokens']) is not int or row['reserved_tokens'] < 1
                or (row['state'] == 'done' and (type(row['reported_tokens']) is not int or row['reported_tokens'] < 0))
                or (row['state'] != 'done' and row['reported_tokens'] is not None)):
            raise ValueError('support_accounting_ledger_invalid')
    return {'path': str(path.resolve()), 'jobs': data['jobs']}


def usage(rows):
    return {'reported': sum(r['reported_tokens'] for r in rows.values() if r['state'] == 'done'),
            'unknown_reserved': sum(r['reserved_tokens'] for r in rows.values()
                                    if r['state'] in ('started', 'unknown'))}


def reserve(state, policy, allowance):
    if not policy.get('accounting'):
        return None
    before = ledger_snapshot(policy)
    if state['unknown_reserved'] or usage(before['jobs'])['unknown_reserved']:
        raise ValueError('support_accounting_unknown_requires_reconciliation')
    if usage(before['jobs'])['reported'] > state['tokens']:
        raise ValueError('support_accounting_prior_usage_not_carried')
    if allowance <= 0:
        raise ValueError('support_token_limit')
    state['unknown_reserved'] += allowance
    return {'reserved_tokens': allowance, 'before': before}


def reconcile(state, policy, hold, result):
    """Called only after run_check has observed termination of its child."""
    try:
        if result.get('execution_finished') is False:
            raise ValueError('support_worker_may_still_be_running')
        after = ledger_snapshot(policy)
        for key, row in hold['before']['jobs'].items():
            current = after['jobs'].get(key)
            # FeatureChat normalizes old done reservations when carrying them.
            if row['state'] == 'done' and (not current or current['state'] != 'done'
                    or current['reported_tokens'] != row['reported_tokens']):
                raise ValueError('support_accounting_history_changed')
            if row['state'] == 'ready' and current and current['state'] != 'ready':
                raise ValueError('support_accounting_prior_slot_reused')
        new = {k: v for k, v in after['jobs'].items() if k not in hold['before']['jobs']}
        delta = usage(new)
        worker = result.get('worker_result')
        if worker and worker.get('ledger') and Path(worker['ledger']).resolve() != Path(after['path']):
            raise ValueError('support_accounting_result_ledger_mismatch')
        state['unknown_reserved'] -= hold['reserved_tokens']
        state['tokens'] += delta['reported']
        state['unknown_reserved'] += delta['unknown_reserved']
        result['accounting'] = {'status': 'reconciled', 'usage': delta, 'ledger': after['path']}
        if worker and worker.get('usage', {'reported': 0, 'unknown_reserved': 0}) != delta:
            result.update(passed=False, accounting_error='support_worker_usage_mismatch')
        if delta['unknown_reserved'] or (not worker and (new or result['timed_out'])):
            result.update(passed=False, outcome_unknown=True)
    except (ValueError, KeyError, TypeError, OSError) as exc:
        # Missing, truncated, rolled-back or substituted ledger is not zero cost.
        result.update(passed=False, outcome_unknown=True,
                      accounting={'status': 'unresolved', 'reason': str(exc),
                                  'held_tokens': hold['reserved_tokens']})
