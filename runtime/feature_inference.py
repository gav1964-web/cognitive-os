"""Sequential budget admission for an adaptive, finite role workflow."""
import json
from pathlib import Path
from uuid import uuid4

from .budgeted_chat import BudgetedChat
from .claim_suite_budget import request_slot, estimate_reservation, check_budget, _read
from .feature_acceptance import save
from .narrow_type_evidence_binding import content_digest
from .local_inference import LocalInferenceError
from .feature_read_response import recover_read


class FeatureChat:
    """Reserve each next call before sending; keep unknown calls fully reserved.

Known settled calls carry reported usage; reservation history remains in events.
Extra upstream-attempt headroom is an estimate, not billing attestation.
"""
    def __init__(self, output, *, max_calls=12, max_input_bytes=80000,
                 carry=None, previous=None, transport=None, budget_limit=1000000,
                 budget_authorization=None, start_new_series=False, known_calls=None):
        if type(budget_limit) is not int or not 1 <= budget_limit <= 10000000:
            raise ValueError('feature_budget_limit_invalid')
        grant = None
        if budget_limit > 1000000:
            from .budget_authorization import load_grant
            grant = load_grant(budget_authorization, budget_limit)
            if carry is None and not start_new_series:
                raise ValueError('extended_feature_budget_requires_carried_ledger')
        if (type(start_new_series) is not bool or start_new_series and
                (carry is not None or (Path(output) / 'budget.json').exists())):
            raise ValueError('new_feature_series_requires_fresh_uncarried_ledger')
        self.budget_limit = budget_limit
        self.output, self.limit = Path(output), max_calls
        self.max_input_bytes, self.transport = max_input_bytes, transport
        self.attempts, self.transcript, self.replayed = [], [], []
        self.unknown_stopped = False
        self.previous = list(previous or [])
        self.known_calls = list(known_calls or previous or [])
        self.ledger = self.output / 'budget.json'
        data = {'schema_version': 'claim_suite_budget.v1', 'limit_exclusive': 1000000,
                'reservation_basis': 'settled reported usage + unknown reserves + next call and two upstream-attempt headrooms',
                'reservation_is_provider_guarantee': False,
                'feature_batch_limit_exclusive': budget_limit, 'jobs': {}}
        if grant:
            data.update(limit_exclusive=budget_limit, budget_authorization=grant)
        if carry:
            old = _read(Path(carry))
            for key, row in old['jobs'].items():
                if row['state'] == 'done':
                    data['jobs'][key] = {**row, 'reserved_tokens': max(1, row['reported_tokens'])}
                elif row['state'] in ('started', 'unknown'):
                    data['jobs'][key] = {**row, 'state': 'unknown', 'reported_tokens': None}
        save(self.ledger, data)

    def __call__(self, messages, *, config):
        if self.unknown_stopped:
            raise ValueError('new_unknown_usage_stops_feature_run')
        if self.previous:
            row = self.previous.pop(0)
            if (row.get('status') == 'returned' and row.get('usage_known')
                    and row['request_digest'] == content_digest(messages)
                    and row['max_output_tokens'] == config.max_output_tokens
                    and all(e.get('requested_model') == config.model for e in row['telemetry'])):
                self.replayed.append(row['request_digest'])
                self.transcript.append(row)
                save(self.output / 'transcript.json', self.transcript)
                save(self.output / 'replayed.json', self.replayed)
                return row['raw_response']
            self.previous.clear()
        if len(self.attempts) >= self.limit:
            raise ValueError('feature_call_count_exhausted')
        if any(row.get('status') == 'returned'
               and row['request_digest'] == content_digest(messages)
               and row['max_output_tokens'] == config.max_output_tokens
               and row.get('response_format') == (config.response_format if isinstance(config.response_format, dict) else None)
               and all(e.get('requested_model') == config.model for e in row['telemetry'])
               for row in self.attempts):
            raise ValueError('feature_repeated_request_without_progress')
        actual_bytes = len(json.dumps(messages, ensure_ascii=False).encode('utf-8'))
        if isinstance(config.response_format, dict):
            actual_bytes += len(json.dumps(config.response_format, ensure_ascii=False).encode('utf-8'))
        if actual_bytes > self.max_input_bytes:
            raise ValueError('feature_request_context_limit')
        limit = config.max_output_tokens
        if type(limit) is not int or not 1 <= limit <= 32768:
            raise ValueError('feature_explicit_output_limit_required')
        slot = request_slot('feature-' + uuid4().hex, max_input_bytes=max(1, actual_bytes),
                            max_output_tokens=limit)
        data = json.loads(self.ledger.read_text(encoding='utf-8'))
        cost = estimate_reservation(slot)
        committed = sum(max(r['reserved_tokens'], r['reported_tokens'] or 0) for r in data['jobs'].values())
        if committed + 3 * cost >= self.budget_limit:
            save(self.output / 'admission-blocked.json', {
                'reason': 'feature_next_call_budget_exhausted', 'provider_label': config.provider_label,
                'request_digest': content_digest(messages), 'input_bytes': actual_bytes,
                'max_output_tokens': limit, 'budget_limit': self.budget_limit,
                'committed': committed, 'remaining': self.budget_limit - committed,
                'next_request_and_upstream_headroom': 3 * cost, 'inference_started': False})
            raise ValueError('feature_next_call_budget_exhausted')
        data['jobs'][slot['digest']] = {'reserved_tokens': cost, 'reported_tokens': None, 'state': 'ready'}
        save(self.ledger, data)
        check_budget(self.ledger, [slot], allow_unknown_reservations=True)
        def persist(rows):
            rows[0]['admission'] = {'committed_before': committed,
                                  'next_request_and_upstream_headroom': 3 * cost}
            save(self.output / 'calls.json', [*self.attempts, *rows])
        adapter = BudgetedChat(self.ledger, [slot], chat=self.transport,
                               allow_unknown_reservations=True, persist=persist)
        try:
            response = adapter(messages, config=config)
        except LocalInferenceError as exc:
            response = recover_read(adapter.attempts[-1]) if adapter.attempts else None
            if str(exc) != 'structured response is not a complete JSON object' or response is None:
                raise
            adapter.attempts[-1].update(status='returned', raw_response=response,
                normalization='two_identical_read_objects_only', original_parser_error=str(exc))
        finally:
            if adapter.attempts:
                row = adapter.attempts[0]
                row['admission'] = {'committed_before': committed,
                                    'next_request_and_upstream_headroom': 3 * cost}
                self.attempts.append(row)
                self.transcript.append(row)
                save(self.output / 'calls.json', self.attempts)
                save(self.output / 'transcript.json', self.transcript)
                settled = json.loads(self.ledger.read_text(encoding='utf-8'))
                entry = settled['jobs'][slot['digest']]
                if not row.get('usage_known'):
                    from .feature_usage import _known_cache_replay
                    evidence = self.known_calls + self.attempts[:-1]
                    evidence = [e for e in evidence if e.get('request_digest') == content_digest(e.get('messages'))]
                    cached = _known_cache_replay(row, evidence)
                    prior_entry = settled['jobs'].get(cached, {})
                    if (cached and prior_entry.get('state') == 'done'
                            and prior_entry.get('reported_tokens', 0) > 0):
                        entry.update(state='done', reported_tokens=0)
                        row.update(usage_known=True, cache_reconciled_from=cached)
                        save(self.output / 'calls.json', self.attempts)
                        save(self.output / 'transcript.json', self.transcript)
                if row.get('usage_known'):
                    entry['reserved_tokens'] = max(1, entry['reported_tokens'])
                else:
                    entry['reserved_tokens'] = 3 * cost
                    self.unknown_stopped = True
                save(self.ledger, settled)
        if not adapter.attempts[-1]['usage_known']:
            raise ValueError('new_unknown_usage_stops_feature_run')
        return response
