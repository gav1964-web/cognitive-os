import json

import pytest

from runtime.feature_inference import FeatureChat
from runtime.feature_usage import reconcile_feature_usage
from runtime.local_inference import LocalInferenceConfig


@pytest.mark.parametrize('complete', [True, False])
def test_reconcile_only_complete_saved_counts_without_rewriting_history(tmp_path, complete):
    calls = []
    def transport(messages, *, config):
        calls.append(1)
        usage = {'prompt_tokens': 2, **({'completion_tokens': 3} if complete else {})}
        config.telemetry_sink({'usage_reported': False, 'usage': usage, **usage})
        raise RuntimeError('empty provider response')
    chat = FeatureChat(tmp_path, transport=transport)
    cfg = LocalInferenceConfig('http://unused', 'fake', max_output_tokens=32768)
    with pytest.raises(RuntimeError):
        chat([{'role': 'user', 'content': 'task'}], config=cfg)
    original = chat.ledger.read_bytes()
    output = tmp_path / 'reconciled.json'
    evidence = reconcile_feature_usage(chat.ledger, tmp_path / 'calls.json', output)
    assert calls == [1] and chat.ledger.read_bytes() == original
    row = next(iter(json.loads(output.read_text())['jobs'].values()))
    assert row['state'] == ('done' if complete else 'unknown')
    assert row['reported_tokens'] == (5 if complete else None)
    assert evidence['provider_called'] is False
    assert bool(evidence['changes']) is complete
    assert json.loads((tmp_path / 'calls.json').read_text())[0]['status'] == 'failed'
    with pytest.raises(ValueError, match='fresh_output'):
        reconcile_feature_usage(chat.ledger, tmp_path / 'calls.json', chat.ledger)


def test_mismatching_transcript_cannot_reconcile(tmp_path):
    from runtime.feature_acceptance import save
    save(tmp_path / 'ledger.json', {'schema_version': 'claim_suite_budget.v1', 'limit_exclusive': 1000000,
        'jobs': {'slot': {'state': 'unknown', 'reserved_tokens': 10000, 'reported_tokens': None}}})
    save(tmp_path / 'calls.json', [{'slot_digest': 'slot', 'request_digest': 'wrong', 'messages': []}])
    with pytest.raises(ValueError, match='request_mismatch'):
        reconcile_feature_usage(tmp_path / 'ledger.json', tmp_path / 'calls.json', tmp_path / 'new.json')
    assert not (tmp_path / 'new.json').exists()


@pytest.mark.parametrize('matches', [True, False])
def test_zero_cache_reconciles_only_matching_known_request_and_response(tmp_path, matches):
    from runtime.feature_acceptance import save
    from runtime.narrow_type_evidence_binding import content_digest
    message = [{'role': 'user', 'content': 'same'}]
    base = {'request_digest': content_digest(message), 'messages': message,
            'max_output_tokens': 32768, 'status': 'returned', 'raw_response': {'result': 'saved'}}
    calls = [{**base, 'slot_digest': 'first', 'usage_known': True,
              'telemetry': [{'requested_model': 'fake', 'total_tokens': 5, 'usage_reported': True}]},
             {**base, 'slot_digest': 'cache', 'usage_known': False,
              'raw_response': {'result': 'saved' if matches else 'different'},
              'telemetry': [{'requested_model': 'fake', 'total_tokens': 0, 'gateway_route': {'cache_hit': True}}]}]
    save(tmp_path / 'calls.json', calls)
    save(tmp_path / 'old.json', {'schema_version': 'claim_suite_budget.v1', 'limit_exclusive': 1000000,
        'jobs': {'first': {'state': 'done', 'reserved_tokens': 5, 'reported_tokens': 5},
                 'cache': {'state': 'unknown', 'reserved_tokens': 10000, 'reported_tokens': None}}})
    reconcile_feature_usage(tmp_path / 'old.json', tmp_path / 'calls.json', tmp_path / 'new.json')
    result = json.loads((tmp_path / 'new.json').read_text())['jobs']['cache']
    assert result['state'] == ('done' if matches else 'unknown')
    assert result['reported_tokens'] == (0 if matches else None)


@pytest.mark.parametrize('matches', [True, False])
def test_feature_chat_accounts_known_cached_response_across_carried_runs(tmp_path, matches):
    def transport(messages, *, config):
        config.telemetry_sink({'requested_model': 'fake', 'total_tokens': 5,
                               'usage_reported': True})
        return {'result': 'original'}
    cfg = LocalInferenceConfig('http://unused', 'fake', max_output_tokens=32768)
    messages = [{'role': 'user', 'content': 'same'}]
    first = FeatureChat(tmp_path / 'first', transport=transport)
    first(messages, config=cfg)

    def cached(messages, *, config):
        config.telemetry_sink({'requested_model': 'fake', 'total_tokens': 0,
                               'usage_reported': True, 'gateway_route': {'cache_hit': True}})
        return {'result': 'original' if matches else 'different'}
    second = FeatureChat(tmp_path / 'second', carry=first.ledger,
                         known_calls=first.attempts, transport=cached)
    if matches:
        assert second(messages, config=cfg) == {'result': 'original'}
        assert second.attempts[-1]['cache_reconciled_from'] == first.attempts[0]['slot_digest']
        assert not second.unknown_stopped
        assert sum(r['reported_tokens'] for r in json.loads(second.ledger.read_text())['jobs'].values()) == 5
    else:
        with pytest.raises(ValueError, match='unknown_usage'):
            second(messages, config=cfg)
        assert second.unknown_stopped
