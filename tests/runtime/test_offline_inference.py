"""Real model transport is never an implicit dependency of runtime tests."""
from urllib import request, error

import pytest

from runtime.local_inference import call_json_chat, LocalInferenceConfig, LocalInferenceError


@pytest.fixture(scope='module')
def prepared_before_function_fixtures():
    with pytest.raises(error.URLError, match='live inference disabled'):
        request.urlopen('https://provider.invalid/v1/chat/completions', timeout=0.01)
    return True


def test_guard_covers_module_fixture_setup(prepared_before_function_fixtures):
    assert prepared_before_function_fixtures


@pytest.mark.parametrize('url', [
    'http://127.0.0.1:8000/v1/chat/completions',
    'https://provider.invalid/v1/chat/completions/',
])
def test_transport_blocked_before_network(offline_inference, url):
    with pytest.raises(error.URLError, match='live inference disabled'):
        request.urlopen(request.Request(url, data=b'{}'), timeout=0.01)
    assert len(offline_inference) == 1


def test_preimported_client_uses_offline_failure(offline_inference):
    with pytest.raises(LocalInferenceError, match='URLError'):
        call_json_chat([{'role': 'user', 'content': 'test'}], config=LocalInferenceConfig(
            base_url='https://provider.invalid/v1', model='test', timeout_seconds=0.01))
    assert offline_inference == ['provider.invalid']


def test_non_model_url_still_works():
    with request.urlopen('data:text/plain,offline-control') as response:
        assert response.read() == b'offline-control'
