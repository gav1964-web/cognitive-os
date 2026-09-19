"""Conservative per-package inference reservations and reported usage accounting."""
from contextlib import contextmanager
import json
from pathlib import Path

from .single_claim_review import review_messages
from .narrow_type_evidence_binding import content_digest

LIMIT = 1_000_000


def estimate_reservation(job):
    # UTF-8 bytes overestimate normal tokenization. Framing/gateway margin is an
    # operational reserve, not a provider-attested upper bound or billing quote.
    if job.get('schema_version') == 'budget_request_slot.v1':
        checked_slot(job)
        return job['max_input_bytes'] + job['max_output_tokens'] + 16384
    encoded = json.dumps(review_messages(job), ensure_ascii=False).encode('utf-8')
    return len(encoded) + 3200 + 16384


def request_slot(label, *, max_input_bytes, max_output_tokens):
    slot = {'schema_version': 'budget_request_slot.v1', 'label': label,
            'max_input_bytes': max_input_bytes, 'max_output_tokens': max_output_tokens}
    slot['digest'] = content_digest(slot)
    checked_slot(slot)
    return slot


def checked_slot(slot):
    if (set(slot) != {'schema_version', 'label', 'max_input_bytes', 'max_output_tokens', 'digest'}
            or slot['schema_version'] != 'budget_request_slot.v1'
            or not isinstance(slot['label'], str) or not slot['label'].strip()
            or any(type(slot[k]) is not int or slot[k] <= 0 for k in ('max_input_bytes', 'max_output_tokens'))
            or slot['digest'] != content_digest({k: v for k, v in slot.items() if k != 'digest'})):
        raise ValueError('invalid_budget_request_slot')


def _write(path, data):
    temporary = path.with_suffix('.pending')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)


@contextmanager
def _locked(path):
    path = Path(path)
    lock = path.with_suffix('.lock')
    with lock.open('x'):
        pass
    try:
        yield path
    finally:
        lock.unlink()


def create_budget(path, jobs):
    path = Path(path)
    rows = {}
    for job in jobs:
        if job['digest'] in rows:
            raise ValueError('budget_duplicate_job')
        rows[job['digest']] = {'reserved_tokens': estimate_reservation(job),
                               'reported_tokens': None, 'state': 'ready'}
    total = sum(r['reserved_tokens'] for r in rows.values())
    if not rows or total >= LIMIT:
        raise ValueError('budget_not_below_million')
    data = {'schema_version': 'claim_suite_budget.v1', 'limit_exclusive': LIMIT,
            'reservation_basis': 'serialized UTF8 bytes or declared byte cap + output cap + framing/gateway reserve16384 per request',
            'reservation_is_provider_guarantee': False, 'jobs': rows}
    path.parent.mkdir(parents=True, exist_ok=True)
    with _locked(path):
        with path.open('x', encoding='utf-8') as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
    return data


def _read(path):
    data = json.loads(path.read_text(encoding='utf-8'))
    if data.get('schema_version') != 'claim_suite_budget.v1' or data.get('limit_exclusive') != LIMIT:
        raise ValueError('invalid_claim_suite_budget')
    if not isinstance(data.get('jobs'), dict) or not data['jobs']:
        raise ValueError('invalid_claim_suite_budget')
    for row in data['jobs'].values():
        if (not isinstance(row, dict) or set(row) != {'state', 'reserved_tokens', 'reported_tokens'}
                or type(row['reserved_tokens']) is not int or row['reserved_tokens'] <= 0
                or row['state'] not in ('ready', 'started', 'unknown', 'done')
                or (row['state'] == 'done' and (type(row['reported_tokens']) is not int or row['reported_tokens'] < 0))
                or (row['state'] != 'done' and row['reported_tokens'] is not None)):
            raise ValueError('invalid_claim_suite_budget')
    return data


def _ready(data, jobs, *, allow_unknown_reservations=False):
    if type(allow_unknown_reservations) is not bool:
        raise ValueError('invalid_unknown_usage_policy')
    blocked = {'started'} if allow_unknown_reservations else {'started', 'unknown'}
    if any(row['state'] in blocked for row in data['jobs'].values()):
        raise ValueError('budget_unresolved_usage')
    if sum(max(r['reserved_tokens'], r['reported_tokens'] or 0) for r in data['jobs'].values()) >= LIMIT:
        raise ValueError('budget_not_below_million')
    for job in jobs:
        row = data['jobs'].get(job['digest'])
        if row is None or row['state'] != 'ready' or row['reserved_tokens'] < estimate_reservation(job):
            raise ValueError('budget_job_not_reserved_or_already_started')


def check_budget(path, jobs, *, allow_unknown_reservations=False):
    with _locked(path) as path:
        data = _read(path)
        _ready(data, jobs, allow_unknown_reservations=allow_unknown_reservations)
        return data


def start_call(path, job, *, allow_unknown_reservations=False):
    with _locked(path) as path:
        data = _read(path)
        _ready(data, [job], allow_unknown_reservations=allow_unknown_reservations)
        data['jobs'][job['digest']]['state'] = 'started'
        _write(path, data)


def settle_call(path, job, telemetry):
    with _locked(path) as path:
        data = _read(path)
        row = data['jobs'][job['digest']]
        if row['state'] != 'started':
            raise ValueError('budget_call_not_started')
        known = bool(telemetry) and all(t.get('usage_reported') is True
            and type(t.get('total_tokens')) is int and t['total_tokens'] > 0 for t in telemetry)
        row.update(state='done' if known else 'unknown',
                   reported_tokens=sum(t['total_tokens'] for t in telemetry) if known else None)
        _write(path, data)
        return known
