"""A failed completion can consume tokens; preserve error and reported usage together."""
import io
import json
from urllib.error import HTTPError

import pytest

from runtime.budgeted_chat import BudgetedChat
from runtime.claim_suite_budget import create_budget, request_slot
from runtime.inference_failure_evidence import failure_evidence
from runtime.local_inference import LocalInferenceConfig, LocalInferenceError, call_json_chat


@pytest.mark.parametrize('usage,known', [
    ({'prompt_tokens':2,'completion_tokens':3,'total_tokens':5}, True),
    ({'prompt_tokens':2,'completion_tokens':3}, True),
    ({'prompt_tokens':2,'completion_tokens':True}, False),
    ({'prompt_tokens':2,'completion_tokens':-3}, False),
    ({'prompt_tokens':2**63-1,'completion_tokens':1}, False),
    (None,False), ({},False), ({'total_tokens':True},False),
    ({'total_tokens':-1},False), ({'total_tokens':'5'},False),
    ({'total_tokens':2**64},False), ({'prompt_tokens':2},False),
])
def test_http_failure_settles_only_actual_reported_counts(tmp_path,monkeypatch,usage,known):
    calls=[]
    payload={'error':{'code':'provider_response_unusable','provider':'deepseek'},
        'provider_diagnostics':{'resolved_model':'deepseek/v3.2','response_status':'empty','secret':'hidden'},
        'usage':usage, 'raw_body':'hidden'}
    def fail(*args,**kwargs):
        calls.append(1)
        raise HTTPError('http://unused.invalid/v1/chat/completions',502,'Bad Gateway',{},
                        io.BytesIO(json.dumps(payload).encode()))
    monkeypatch.setattr('runtime.local_inference.request.urlopen',fail)
    slot=request_slot('offline',max_input_bytes=1000,max_output_tokens=100)
    ledger=tmp_path/'budget.json'
    create_budget(ledger,[slot])
    events=[]
    chat=BudgetedChat(ledger,[slot],chat=call_json_chat,persist=lambda rows:events.append(rows))
    cfg=LocalInferenceConfig('http://unused.invalid/v1','deepseek/chat',max_output_tokens=100)
    with pytest.raises(LocalInferenceError) as caught:
        chat([{'role':'user','content':'private prompt'}],config=cfg)
    assert calls==[1]
    row=events[-1][0]
    assert row['status']=='failed' and row['usage_known'] is known
    settled=json.loads(ledger.read_text())['jobs'][slot['digest']]
    assert settled['state']==('done' if known else 'unknown')
    assert settled['reported_tokens']==(5 if known else None)
    evidence=failure_evidence(caught.value)
    assert evidence['quality_evaluation']=='not_evaluated'
    assert evidence['provider_failure']['diagnostics']['resolved_model']=='deepseek/v3.2'
    assert 'hidden' not in str(evidence)
    if known:
        assert evidence['usage']=={**usage, 'total_tokens': 5}
        assert row['telemetry'][0]['total_tokens']==5
