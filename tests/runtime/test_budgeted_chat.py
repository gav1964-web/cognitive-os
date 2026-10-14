"""Adaptive requests share the package budget; no real inference in tests."""
from dataclasses import replace
import json

import pytest

from runtime.budgeted_chat import BudgetedChat
from runtime.claim_suite_budget import create_budget, request_slot, check_budget
from runtime.project_description import description_model_config


@pytest.fixture
def setup(tmp_path):
    slots = [request_slot(str(n), max_input_bytes=300, max_output_tokens=100) for n in range(3)]
    ledger = tmp_path / 'budget.json'
    create_budget(ledger, slots)
    config = replace(description_model_config(), fallbacks=(), max_output_tokens=100)
    return ledger, slots, config


def test_actual_usage_forwarded_and_requests_persist_before_call(setup):
    ledger, slots, config = setup
    events, reports, calls = [], [], []
    def chat(messages, *, config):
        assert reports[-1][-1]['status'] == 'started'
        calls.append(messages)
        config.telemetry_sink({'usage_reported': True, 'total_tokens': 90})
        return {'received': True}
    wrapped = BudgetedChat(ledger, slots, chat=chat, persist=reports.append)
    for n in range(3):
        assert wrapped([{'role': 'user', 'content': str(n)}], config=replace(config, telemetry_sink=events.append))
    with pytest.raises(ValueError, match='count_exceeded'):
        wrapped([], config=config)
    assert len(calls) == len(events) == 3
    assert all(r['state'] == 'done' for r in json.loads(ledger.read_text())['jobs'].values())
    with pytest.raises(ValueError, match='already_started'):
        BudgetedChat(ledger, slots, chat=chat)


@pytest.mark.parametrize('kind', ['unknown', 'exception'])
def test_unknown_or_interrupted_attempt_blocks_other_slots(setup, kind):
    ledger, slots, config = setup
    def chat(*args, **kwargs):
        if kind == 'exception':
            raise OSError('connection lost')
        return {}
    wrapped = BudgetedChat(ledger, slots, chat=chat)
    with pytest.raises((ValueError, OSError)):
        wrapped([], config=config)
    with pytest.raises(ValueError, match='unresolved_usage'):
        check_budget(ledger, slots[1:])
    assert not wrapped.attempts[0]['usage_known']


@pytest.mark.parametrize('kind', ['input', 'output', 'fallback'])
def test_bounds_fail_before_any_provider_call(setup, kind):
    ledger, slots, config = setup
    messages = [{'role': 'user', 'content': 'x' * 400}] if kind == 'input' else []
    if kind == 'output': config = replace(config, max_output_tokens=101)
    if kind == 'fallback': config = replace(config, fallbacks=(config,))
    wrapped = BudgetedChat(ledger, slots, chat=lambda *a, **k: pytest.fail('No oversized call'))
    with pytest.raises(ValueError, match='bounds_exceeded'):
        wrapped(messages, config=config)
    assert not wrapped.attempts
    check_budget(ledger, slots)


def test_explicit_unknown_policy_preserves_raw_answer_and_unknown_usage(setup):
    ledger, slots, config = setup
    wrapped = BudgetedChat(ledger, slots, chat=lambda *a, **k:{'answer':'available'},
                           allow_unknown_reservations=True)
    for _ in slots:
        assert wrapped([], config=config) == {'answer':'available'}
    assert all(r['state']=='unknown' and r['reported_tokens'] is None
               for r in json.loads(ledger.read_text())['jobs'].values())
    assert all(not r['usage_known'] and r['allow_unknown_reservations'] for r in wrapped.attempts)
