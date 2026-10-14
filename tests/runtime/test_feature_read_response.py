"""Only two identical read requests may be normalized; decisions stay strict."""
import json
from dataclasses import replace

import pytest

from runtime.feature_read_response import duplicated_read
from runtime.feature_inference import FeatureChat
from runtime.local_inference import LocalInferenceError
from tests.runtime.test_feature_inference import config


@pytest.mark.parametrize('suffix', ['different', 'approve', 'comment', 'third'])
def test_ambiguous_or_authoritative_responses_are_rejected(suffix):
    read = {'status': 'read', 'reads': [{'path': 'engine.py'}]}
    text = json.dumps(read)
    if suffix == 'different': text += json.dumps({**read, 'reads': [{'path': 'other.py'}]})
    if suffix == 'approve': text = json.dumps({'status': 'ready', 'decision': 'approve'}) * 2
    if suffix == 'comment': text += ' (No) ' + text
    if suffix == 'third': text *= 3
    assert duplicated_read(text) is None


def test_duplicate_read_retains_usage_raw_evidence_and_normalization(tmp_path):
    read = {'status': 'read', 'reads': [{'path': 'engine.py', 'start': 1, 'end': 2}]}
    raw = json.dumps(read) + '\n\n' + json.dumps(read)
    def transport(messages, *, config):
        config.raw_response_sink({'content': raw})
        config.telemetry_sink({'usage_reported': True, 'total_tokens': 57,
                               'requested_model': config.model})
        raise LocalInferenceError('structured response is not a complete JSON object')
    chat = FeatureChat(tmp_path, transport=transport)
    assert chat([], config=replace(config(), max_output_tokens=2048)) == read
    row = chat.attempts[0]
    assert row['normalization'] == 'two_identical_read_objects_only'
    assert row['response_evidence'][0]['content'] == raw
    assert next(iter(json.loads(chat.ledger.read_text())['jobs'].values()))['reported_tokens'] == 57
