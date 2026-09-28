import json

import pytest

from runtime.feature_inference import FeatureChat
from runtime.feature_workspace import merge_reads
from runtime.local_inference import LocalInferenceConfig


def config():
    return LocalInferenceConfig('http://unused', 'fake', max_output_tokens=32768)


def success(messages, *, config):
    config.telemetry_sink({'requested_model': 'fake', 'total_tokens': 37, 'usage_reported': True})
    return {'status': 'ready'}


def test_sequential_admission_preserves_actual_usage_and_call_limit(tmp_path):
    chat = FeatureChat(tmp_path, max_calls=2, transport=success)
    for number in range(2):
        assert chat([{'role': 'user', 'content': f'goal{number}'}], config=config())['status'] == 'ready'
    with pytest.raises(ValueError, match='call_count'):
        chat([], config=config())
    rows = json.loads(chat.ledger.read_text())['jobs'].values()
    assert sum(r['reported_tokens'] for r in rows) == 74
    assert all(r['reserved_tokens'] == 37 for r in rows)
    assert len(chat.transcript) == 2
    assert chat.attempts[1]['admission']['committed_before'] == 37


def test_repeating_identical_rejected_request_never_calls_gateway_again(tmp_path):
    chat = FeatureChat(tmp_path, transport=success)
    messages = [{'role': 'user', 'content': 'same feedback'}]
    chat(messages, config=config())
    with pytest.raises(ValueError, match='repeated_request_without_progress'):
        chat(messages, config=config())
    assert len(chat.attempts) == 1


def test_unknown_usage_keeps_full_attempt_headroom(tmp_path):
    chat = FeatureChat(tmp_path, transport=lambda messages, config: {'status': 'ready'})
    with pytest.raises(ValueError, match='unknown_usage'):
        chat([], config=config())
    row = next(iter(json.loads(chat.ledger.read_text())['jobs'].values()))
    assert row['state'] == 'unknown' and row['reported_tokens'] is None
    assert row['reserved_tokens'] == 3 * (len(json.dumps([])) + 32768 + 16384)
    with pytest.raises(ValueError, match='unknown_usage'):
        chat([], config=config())
    assert len(chat.attempts) == 1


def test_historical_unknown_cannot_be_forgotten_at_next_admission(tmp_path):
    old = tmp_path / 'old.json'
    old.write_text(json.dumps({'schema_version': 'claim_suite_budget.v1', 'limit_exclusive': 1000000,
                              'jobs': {'past': {'state': 'unknown', 'reserved_tokens': 900000,
                                               'reported_tokens': None}}}))
    output = tmp_path / 'next'
    output.mkdir()
    chat = FeatureChat(output, carry=old, transport=success)
    with pytest.raises(ValueError, match='next_call_budget'):
        chat([], config=config())
    assert not chat.attempts


def test_smaller_batch_limit_is_enforced_before_transport(tmp_path):
    chat = FeatureChat(tmp_path, budget_limit=100000, transport=success)
    with pytest.raises(ValueError, match='next_call_budget'):
        chat([], config=config())
    assert not chat.attempts
    receipt = json.loads((tmp_path / 'admission-blocked.json').read_text())
    assert receipt['remaining'] == 100000 and receipt['inference_started'] is False
    assert receipt['max_output_tokens'] == 32768
    assert receipt['next_request_and_upstream_headroom'] == 3 * (2 + 32768 + 16384)


def test_explicit_smaller_output_cap_is_sent_and_reserved_without_resetting_budget(tmp_path):
    from dataclasses import replace
    def transport(messages, *, config):
        assert config.max_output_tokens == 16384
        return success(messages, config=config)
    chat = FeatureChat(tmp_path, budget_limit=100000, transport=transport)
    assert chat([], config=replace(config(), max_output_tokens=16384))['status'] == 'ready'
    row = chat.attempts[0]
    assert row['max_output_tokens'] == 16384
    assert row['admission']['next_request_and_upstream_headroom'] == 3 * (2 + 16384 + 16384)


def test_overlapping_reads_are_merged_without_losing_earlier_lines():
    base = {'path': 'module.py', 'sha256': 'abc', 'total_lines': 5}
    rows = merge_reads([{**base, 'start': 1, 'end': 3, 'content': 'a\nb\nc\n'}],
                      [{**base, 'start': 3, 'end': 5, 'content': 'c\nd\ne\n'}])
    assert len(rows) == 1 and rows[0]['content'] == 'a\nb\nc\nd\ne\n'
    assert rows[0]['start'] == 1 and rows[0]['end'] == 5


def test_citation_context_cannot_invent_unobserved_lines():
    from runtime.feature_workspace import cited_sources
    sources = [{'path': 'module.py', 'sha256': 'abc', 'total_lines': 10,
                'start': 3, 'end': 5, 'content': 'c\nd\ne\n'}]
    rows = cited_sources(sources, [{'path': 'module.py', 'start': 1, 'end': 4}])
    assert rows[0]['start'] == 3 and rows[0]['end'] == 4
    assert rows[0]['content'] == 'c\nd\n'
