"""The generic client rejects invalid output limits before HTTP, also with failover."""
import io
import json
from dataclasses import replace

import pytest

from runtime.local_inference import LocalInferenceConfig, LocalInferenceError, call_json_chat


@pytest.mark.parametrize('fallback', [False, True])
@pytest.mark.parametrize('value', [True, False, 0, -1, 1.0, 1.5, '8', [], {}, float('nan'), float('inf')])
def test_invalid_limit_does_not_contact_primary_or_backup(monkeypatch, value, fallback):
    def unexpected(*args, **kwargs):
        pytest.fail('invalid local option must not cause HTTP')
    monkeypatch.setattr('runtime.local_inference.request.urlopen', unexpected)
    cfg = LocalInferenceConfig(base_url='http://primary.invalid', model='primary', max_output_tokens=value)
    if fallback:
        cfg = replace(cfg, fallbacks=(replace(cfg, model='backup', max_output_tokens=100),))
    with pytest.raises(LocalInferenceError, match='max_output_tokens'):
        call_json_chat([], config=cfg)


@pytest.mark.parametrize('value', [None, 1, 32768, 65536])
def test_valid_limit_has_no_provider_specific_ceiling(monkeypatch, value):
    requests = []
    def respond(req, **kwargs):
        requests.append(json.loads(req.data))
        return io.BytesIO(b'{"choices":[{"message":{"content":"{}"}}]}')
    monkeypatch.setattr('runtime.local_inference.request.urlopen', respond)
    cfg = LocalInferenceConfig(base_url='http://primary.invalid', model='primary', max_output_tokens=value)
    assert call_json_chat([], config=cfg) == {}
    assert len(requests) == 1
    assert ('max_tokens' in requests[0]) == (value is not None)
    if value is not None:
        assert requests[0]['max_tokens'] == value
