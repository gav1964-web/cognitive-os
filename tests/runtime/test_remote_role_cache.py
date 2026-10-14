"""Service continuation retains paid evidence without trusting arbitrary cache hits."""
import pytest

from runtime.feature_inference import FeatureChat
from runtime.local_inference import LocalInferenceConfig
from runtime.remote_role_job import load_known_calls, ledger_usage
from runtime.remote_support_protocol import digest, load, save


@pytest.mark.parametrize('mismatch', [None, 'response', 'request', 'model', 'unpaid'])
def test_bound_history_reconciles_only_an_accounted_exact_cache_hit(tmp_path, mismatch):
    config = LocalInferenceConfig('http://unused', 'fake', max_output_tokens=32768)
    messages = [{'role': 'user', 'content': 'repair the mapper'}]

    def paid(messages, *, config):
        config.telemetry_sink({'requested_model': 'fake', 'total_tokens': 37, 'usage_reported': True})
        return {'status': 'ready'}

    prior = tmp_path / 'prior'
    prior.mkdir()
    old = FeatureChat(prior, transport=paid)
    old(messages, config=config)
    calls = prior / 'calls.json'
    job = {'known_calls': {str(calls): digest(calls.read_bytes())}}
    carry = old.ledger
    if mismatch == 'unpaid':
        data = load(carry)
        data['jobs'] = {'unrelated': {'state': 'done', 'reported_tokens': 37, 'reserved_tokens': 37}}
        carry = tmp_path / 'empty-ledger.json'
        save(carry, data)

    def cached(messages, *, config):
        config.telemetry_sink({'requested_model': 'different' if mismatch == 'model' else 'fake',
                               'total_tokens': 0, 'usage_reported': True,
                               'gateway_route': {'cache_hit': True}})
        return {'status': 'different' if mismatch == 'response' else 'ready'}

    output = tmp_path / 'next'
    output.mkdir()
    chat = FeatureChat(output, carry=carry, transport=cached, known_calls=load_known_calls(job))
    if mismatch == 'request':
        messages = [{'role': 'user', 'content': 'another task'}]
    if mismatch is None:
        assert chat(messages, config=config) == {'status': 'ready'}
        assert ledger_usage(chat.ledger) == {'reported': 37, 'unknown_reserved': 0}
        assert chat.attempts[0]['cache_reconciled_from'] == old.attempts[0]['slot_digest']
        assert not chat.replayed  # A fresh transport response, not local decision replay.
    else:
        with pytest.raises(ValueError, match='new_unknown_usage'):
            chat(messages, config=config)
        assert ledger_usage(chat.ledger)['unknown_reserved'] > 0


def test_modified_or_invented_history_is_rejected(tmp_path):
    calls = tmp_path / 'calls.json'
    save(calls, [])
    job = {'known_calls': {str(calls): digest(calls.read_bytes())}}
    save(calls, [{'request_digest': 'invented', 'messages': []}])
    with pytest.raises(ValueError, match='known_calls_changed'):
        load_known_calls(job)
    job['known_calls'][str(calls)] = digest(calls.read_bytes())
    with pytest.raises(ValueError, match='known_calls_invalid'):
        load_known_calls(job)
    assert load_known_calls({}) == []  # Existing jobs remain valid.
