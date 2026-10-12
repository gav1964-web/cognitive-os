"""Cooperative stops preserve settled usage and never hide an unknown call."""
import json

import pytest

from runtime.feature_inference import FeatureChat
from tests.runtime.test_feature_inference import config, success


def test_preexisting_stop_makes_no_reservation_and_no_transport_call(tmp_path):
    def forbidden(*args, **kwargs):
        pytest.fail('transport was called after STOP')
    stop = tmp_path / 'custom-stop'
    stop.touch()
    chat = FeatureChat(tmp_path, transport=forbidden, stop_file=stop)
    before = chat.ledger.read_bytes()
    with pytest.raises(ValueError, match='feature_stop_requested'):
        chat([], config=config())
    assert chat.ledger.read_bytes() == before and not chat.attempts
    receipt = json.loads((tmp_path / 'stop-receipt.json').read_text())
    assert receipt['completed_calls'] == 0 and receipt['inference_started'] is False


def test_stop_during_call_allows_reply_and_usage_then_blocks_next_call(tmp_path):
    def transport(messages, *, config):
        (tmp_path / 'STOP').touch()
        return success(messages, config=config)
    chat = FeatureChat(tmp_path, transport=transport)
    assert chat([], config=config()) == {'status': 'ready'}
    before = chat.ledger.read_bytes()
    with pytest.raises(ValueError, match='feature_stop_requested'):
        chat([{'role': 'user', 'content': 'next stage'}], config=config())
    assert chat.ledger.read_bytes() == before
    jobs = json.loads(before)['jobs']
    assert len(jobs) == 1 and next(iter(jobs.values()))['reported_tokens'] == 37
    assert len(chat.transcript) == 1 and chat.transcript[0]['raw_response'] == {'status': 'ready'}
    receipt = json.loads((tmp_path / 'stop-receipt.json').read_text())
    assert receipt['completed_calls'] == 1 and not receipt['in_flight_call_cancelled']
    next_chat = FeatureChat(tmp_path / 'next', carry=chat.ledger, transport=success)
    assert next_chat([], config=config()) == {'status': 'ready'}
    assert sum(r['reported_tokens'] for r in json.loads(next_chat.ledger.read_text())['jobs'].values()) == 74


def test_unknown_reply_stays_unknown_even_if_stop_was_requested(tmp_path):
    def transport(messages, *, config):
        (tmp_path / 'STOP').touch()
        return {'status': 'ready'}
    chat = FeatureChat(tmp_path, transport=transport)
    for _ in range(2):
        with pytest.raises(ValueError, match='new_unknown_usage_stops_feature_run'):
            chat([], config=config())
    entry = next(iter(json.loads(chat.ledger.read_text())['jobs'].values()))
    assert entry['state'] == 'unknown' and entry['reported_tokens'] is None
    assert entry['reserved_tokens'] > 32768 and len(chat.attempts) == 1
    assert not (tmp_path / 'stop-receipt.json').exists()


def test_stop_precedes_cached_replay_without_consuming_it(tmp_path):
    first = FeatureChat(tmp_path / 'first', transport=success)
    first([], config=config())
    second = FeatureChat(tmp_path / 'second', previous=first.transcript, carry=first.ledger)
    second.stop_file.touch()
    with pytest.raises(ValueError, match='feature_stop_requested'):
        second([], config=config())
    assert len(second.previous) == 1 and not second.transcript and not second.replayed
