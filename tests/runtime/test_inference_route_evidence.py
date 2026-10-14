from email.message import Message
from unittest.mock import patch

import pytest

from runtime.inference_route_evidence import route_evidence
from runtime.local_inference import LocalInferenceConfig, call_json_chat
from tests.runtime.test_local_inference import _FakeResponse


def test_gateway_metadata_survives_transport_with_unknown_billing():
    response = _FakeResponse({'model':'test','choices':[{'message':{'content':'{"ok":true}'}}],
                             'usage':{'total_tokens':0}})
    response.headers=Message()
    for name,value in {'x-cache-hit':'1','X-Route-Requested-Model':'deepseek/chat',
                       'X-Route-Resolved-Profile':'primary','X-Route-Attempted-Models':'primary,backup',
                       'Authorization':'secret','Set-Cookie':'secret','X-Request-Duration-Seconds':'0.25'}.items():
        response.headers[name]=value
    records=[]
    with patch('runtime.local_inference.request.urlopen',return_value=response):
        assert call_json_chat([],config=LocalInferenceConfig(base_url='http://example.invalid',model='test',
                                                           telemetry_sink=records.append)) == {'ok':True}
    row=records[0]
    assert row['gateway_route']['cache_hit'] is True
    assert row['gateway_route']['attempted_models']==['primary','backup']
    assert row['total_tokens']==0
    assert row['billing_evidence'].startswith('unknown')
    assert 'secret' not in str(row)


@pytest.mark.parametrize('value',['x\nsecret','x'*161,'<script>','a,b,c,d,e,f,g,h,i'])
def test_unbounded_or_unsafe_metadata_is_discarded(value):
    assert route_evidence({'X-Route-Attempted-Models':value})=={}


@pytest.mark.parametrize('duration',['nan','inf','-1','99999999'])
def test_invalid_durations_are_not_reported(duration):
    assert route_evidence({'X-Request-Duration-Seconds':duration})=={}


def test_missing_metadata_does_not_imply_cache_miss():
    assert route_evidence(None)=={}
    assert route_evidence({'X-Cache-Hit':'unknown'})=={}
