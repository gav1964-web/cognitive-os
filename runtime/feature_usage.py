"""Reconcile saved, locally trusted provider telemetry without another request."""
import json
from pathlib import Path

from .claim_suite_budget import _read
from .feature_acceptance import save
from .feature_workspace import digest
from .inference_failure_evidence import checked_usage
from .narrow_type_evidence_binding import content_digest


def _known_cache_replay(call, previous):
    events = call.get('telemetry', [])
    if (call.get('status') != 'returned' or not events
            or not all(e.get('gateway_route', {}).get('cache_hit') is True
                       and e.get('total_tokens') == 0 for e in events)):
        return None
    for old in previous:
        if (old.get('status') == 'returned' and old.get('usage_known') is True
                and all(old.get(k) == call.get(k) for k in
                        ('request_digest', 'max_output_tokens', 'response_format_digest', 'raw_response'))
                and [e.get('requested_model') for e in old['telemetry']]
                    == [e.get('requested_model') for e in events]):
            return old['slot_digest']
    return None


def reconcile_feature_usage(ledger, calls, output):
    ledger, calls, output = Path(ledger), Path(calls), Path(output)
    if output.exists() or output.resolve() in (ledger.resolve(), calls.resolve()):
        raise ValueError('usage_reconciliation_requires_fresh_output')
    data = _read(ledger)
    rows = json.loads(calls.read_text(encoding='utf-8'))
    changes, seen = [], set()
    for ordinal, call in enumerate(rows):
        key = call['slot_digest']
        if key in seen or key not in data['jobs']:
            raise ValueError('usage_reconciliation_slot_mismatch')
        seen.add(key)
        if call['request_digest'] != content_digest(call['messages']):
            raise ValueError('usage_reconciliation_request_mismatch')
        entry = data['jobs'][key]
        if entry['state'] != 'unknown' or call['status'] not in ('failed', 'returned'):
            continue
        events = call.get('telemetry', [])
        usage = [checked_usage(e.get('usage', e)) for e in events]
        cached_from = _known_cache_replay(call, rows[:ordinal])
        cached_entry = data['jobs'].get(cached_from, {})
        if cached_from and cached_entry.get('state') == 'done' and cached_entry.get('reported_tokens', 0) > 0:
            changes.append({'slot_digest': key, 'before': dict(entry), 'reported_tokens': 0,
                            'basis': 'gateway-reported cache replay matching a previously accounted request/response',
                            'known_response_slot': cached_from})
            entry.update(state='done', reported_tokens=0, reserved_tokens=1)
            continue
        if not usage or not all(u and type(u.get('total_tokens')) is int
                                and u['total_tokens'] > 0 for u in usage):
            continue
        for event, counts in zip(events, usage):
            for name in ('prompt_tokens', 'completion_tokens', 'total_tokens'):
                if name in event and name in counts and event[name] != counts[name]:
                    raise ValueError('usage_reconciliation_conflicting_counts')
        total = sum(u['total_tokens'] for u in usage)
        changes.append({'slot_digest': key, 'before': dict(entry),
                        'reported_tokens': total, 'usage': usage,
                        'basis': 'reported total or sum of reported prompt/completion; request outcome unchanged'})
        entry.update(state='done', reported_tokens=total, reserved_tokens=max(1, total))
    data['reconciliation'] = {'ledger': str(ledger.resolve()), 'ledger_sha256': digest(ledger.read_bytes()),
                              'calls': str(calls.resolve()), 'calls_sha256': digest(calls.read_bytes()),
                              'changes': changes, 'provider_called': False}
    save(output, data)
    return data['reconciliation']
