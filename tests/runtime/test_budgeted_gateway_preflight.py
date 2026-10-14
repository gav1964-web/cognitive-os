"""A missing managed listener must be bootstrapped before reserving a live call."""
from dataclasses import replace
import json

import pytest

from runtime.budgeted_chat import BudgetedChat
from runtime.claim_suite_budget import create_budget, request_slot
from runtime.local_inference import LocalInferenceConfig, LocalInferenceError


def setup_budget(tmp_path):
    ledger = tmp_path/'budget.json'
    slots = [request_slot('request', max_input_bytes=1000, max_output_tokens=100)]
    create_budget(ledger, slots)
    config = replace(LocalInferenceConfig.from_l45_env(), fallbacks=(), max_output_tokens=100)
    return ledger, slots, config


@pytest.mark.parametrize('status', ['already_running', 'started', 'not_required'])
def test_real_transport_checks_gateway_before_call_and_records_receipt(tmp_path, monkeypatch, status):
    ledger, slots, config = setup_budget(tmp_path)
    events = []
    def ensure(root, url):
        assert all(r['state'] == 'ready' for r in json.loads(ledger.read_text())['jobs'].values())
        assert url == config.base_url
        events.append('ready')
        return {'status': status, 'checked': status != 'not_required'}
    def chat(messages, *, config):
        assert events == ['ready']
        events.append('inference')
        config.telemetry_sink({'usage_reported': True, 'total_tokens': 20})
        return {'ok': True}
    monkeypatch.setattr('runtime.budgeted_chat.ensure_llm_gateway_for_url', ensure)
    monkeypatch.setattr('runtime.budgeted_chat.call_json_chat', chat)
    wrapper = BudgetedChat(ledger, slots)
    assert wrapper([], config=config) == {'ok': True}
    assert wrapper.attempts[0]['gateway_preflight']['status'] == status
    assert events == ['ready', 'inference']


def test_failed_bootstrap_does_not_spend_or_poison_inference_slot(tmp_path, monkeypatch):
    ledger, slots, config = setup_budget(tmp_path)
    monkeypatch.setattr('runtime.budgeted_chat.ensure_llm_gateway_for_url', lambda *a: {'status': 'failed'})
    monkeypatch.setattr('runtime.budgeted_chat.call_json_chat', lambda *a, **k: pytest.fail('must not call'))
    wrapper = BudgetedChat(ledger, slots)
    with pytest.raises(LocalInferenceError, match='before inference'):
        wrapper([], config=config)
    assert wrapper.attempts == []
    assert all(r['state'] == 'ready' for r in json.loads(ledger.read_text())['jobs'].values())


def test_injected_transport_does_not_launch_a_real_gateway(tmp_path, monkeypatch):
    ledger, slots, config = setup_budget(tmp_path)
    monkeypatch.setattr('runtime.budgeted_chat.ensure_llm_gateway_for_url', lambda *a: pytest.fail('injected transport'))
    def fixture_chat(messages, *, config):
        config.telemetry_sink({'usage_reported': True, 'total_tokens': 10})
        return {}
    wrapper = BudgetedChat(ledger, slots, chat=fixture_chat)
    wrapper([], config=config)
    assert 'gateway_preflight' not in wrapper.attempts[0]


def test_gateway_output_limit_is_checked_before_inference_accounting(tmp_path, monkeypatch):
    ledger, slots, config = setup_budget(tmp_path)
    monkeypatch.setattr('runtime.budgeted_chat.ensure_llm_gateway_for_url',
                        lambda *a: {'status': 'already_running', 'max_output_tokens': 99})
    monkeypatch.setattr('runtime.budgeted_chat.call_json_chat', lambda *a, **k: pytest.fail('must not call'))
    wrapper = BudgetedChat(ledger, slots)
    with pytest.raises(LocalInferenceError, match='output limit'):
        wrapper([], config=config)
    assert not wrapper.attempts
    assert all(r['state'] == 'ready' for r in json.loads(ledger.read_text())['jobs'].values())
