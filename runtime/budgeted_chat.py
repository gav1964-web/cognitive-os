"""Bound an adaptive description sequence using the shared package ledger."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path

from .claim_suite_budget import checked_slot, check_budget, start_call, settle_call
from .local_inference import call_json_chat, LocalInferenceError
from .llm_gateway_bootstrap import ensure_llm_gateway_for_url
from .narrow_type_evidence_binding import content_digest


class BudgetedChat:
    def __init__(self, ledger, slots, *, chat=None, persist=None, allow_unknown_reservations=False):
        if not slots:
            raise ValueError('budget_slots_required')
        for slot in slots:
            checked_slot(slot)
        check_budget(ledger, slots, allow_unknown_reservations=allow_unknown_reservations)
        self.allow_unknown_reservations = allow_unknown_reservations
        self.ledger = ledger
        self.slots = deepcopy(slots)
        self.chat = chat or call_json_chat
        self.managed_transport = chat is None
        self.persist = persist or (lambda attempts: None)
        self.attempts = []
        self.gateway_preflight = None

    def __call__(self, messages, *, config):
        if len(self.attempts) >= len(self.slots):
            raise ValueError('budget_request_count_exceeded')
        slot = self.slots[len(self.attempts)]
        size = len(json.dumps(messages, ensure_ascii=False).encode('utf-8'))
        if (config.fallbacks or type(config.max_output_tokens) is not int
                or not 0 < config.max_output_tokens <= slot['max_output_tokens']
                or size > slot['max_input_bytes']):
            raise ValueError('budget_request_bounds_exceeded')
        if self.managed_transport:
            self.gateway_preflight = ensure_llm_gateway_for_url(
                Path(__file__).resolve().parents[1], config.base_url)
            if self.gateway_preflight['status'] == 'failed':
                raise LocalInferenceError('managed gateway readiness failed before inference')
            limit = self.gateway_preflight.get('max_output_tokens')
            if limit is not None and config.max_output_tokens > limit:
                raise LocalInferenceError('managed gateway output limit exceeded before inference')
        start_call(self.ledger, slot, allow_unknown_reservations=self.allow_unknown_reservations)
        row = {'slot_digest': slot['digest'], 'status': 'started',
               'request_digest': content_digest(messages), 'messages': deepcopy(messages),
               'input_bytes': size, 'max_output_tokens': config.max_output_tokens,
               'telemetry': [], 'allow_unknown_reservations': self.allow_unknown_reservations}
        if self.gateway_preflight is not None:
            row['gateway_preflight'] = deepcopy(self.gateway_preflight)
        self.attempts.append(row)
        self.persist(deepcopy(self.attempts))
        def record(event):
            row['telemetry'].append(deepcopy(event))
            if config.telemetry_sink:
                config.telemetry_sink(event)
        try:
            response = self.chat(messages, config=replace(config, telemetry_sink=record))
            row.update(status='returned', raw_response=deepcopy(response))
        except Exception as exc:
            row.update(status='failed', error_kind=type(exc).__name__)
            raise
        finally:
            known = settle_call(self.ledger, slot, row['telemetry'])
            row['usage_known'] = known
            self.persist(deepcopy(self.attempts))
        if not known and not self.allow_unknown_reservations:
            raise ValueError('budget_unresolved_usage')
        return response
